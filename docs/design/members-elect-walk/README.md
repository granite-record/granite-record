# Members-Elect after the walk of dry run 7 (8 November 2026)

Alice's walk of dry run 7 (https://2663f3e0.graniterecord.pages.dev, dev
aa4d8582), as the laptop manager set it out in six items, for Sunday. Branch
`fix/members-elect-walk`, off aa4d8582. **All six items are done.**

## What a reader sees

**1. Two views.** Members-Elect is **By last name** and **By county**. By
district has gone. Its "Result not final — a recount was requested" is now
said in two places:

- **Under "Who won the seats"**, a fold: "19 seats not final, in 16
  districts". Opened, it says "A recount was requested in each." and names
  them: "Belknap District 6", …, "Cheshire District 18 — 2 seats", ….
- **In By county**, as before: the county's summary counts them ("Belknap 17
  1 not final") and a line under its members names them ("Result not final in
  District 6 — a recount was requested").

By last name says it once under its House heading: "Result not final for 19
seats in 16 districts — a recount was requested in each. Who won the seats
lists them, and By county." A race not final has no member-elect in the file,
so there is no chip to put the words on.

Every address By district had now lands on By county:

- `#pane-edist` and `#tab-edist` open By county, and the address bar says
  `#pane-ecounty`.
- `#of-eld-senate` and `#of-eld-house` are By county's two chamber headings
  now.
- A link followed while the page is open (Legislators showing, then
  `#of-eld-senate`) opens Members-Elect, By county, and scrolls to the
  heading.

On dry run 7 all four left the reader on By last name.

**2. Tab order:** My Town | Legislators (406) | Members-Elect (405) | Federal |
Executive | Judicial | County. The panels are in the same order.

**3. The chip.** Each member-elect is the Legislators tab's chip: the same
component, the same tag ("Rep.-elect Thomas Cormen (D - Graf 17)"), linked
where the file links them. "Rep.-elect" stays. The word is no longer inside
the chip; it sits beside it.

The Members-Elect lists are in columns of at least 544px, or one column, so
a chip and its word fit on one line. That gives two columns at 1280; the
Legislators tab has three of 364px. In 364px columns, 322 of the 405 words
went under their chips at 1280, and at 900–1024px most chips wrapped. On a
phone, where the two don't fit on one line, the word goes on its own line
just under the chip.

| Chips on one line (By last name, 405) | 375px | 390px | 1024px | 1280px |
|---|---|---|---|---|
| Dry run 7 | 35 | 67 | — | 83 |
| This branch | 354 | 378 | 405 | 405 |
| This branch, two lines where the Legislators chip is one | 27 | 13 | 0 | 0 |

**Where the word sits on this branch:**

- **From 980 to 1440px, beside every chip.** Measured every 10px, in English
  and Spanish, in both views.
- **At 390,** beside 67 chips and under 338.

The Legislators tab has 404 of 406 chips on one line at every width. For the
13 at 390, see *For Alice to decide*.

**4. The words**, in capitals:

| The file says | The word | On dry run 7 |
|---|---|---|
| sitting, re-elected to the seat they hold | **RETURNING** | 206 |
| former, elected again to the chamber they last sat in | **RETURNING** | 24 |
| sitting, elected to another district of the same chamber | **NEW DISTRICT** | 5 |
| sitting or former, elected to the other chamber | **NEW CHAMBER** | 2 (Creighton, Telerski: House to Senate) |
| linked to nobody on the rosters | **NEW** | 168 |

They replace Re-elected, New seat, Returning and New. Every one of the 405
gets a word.

**What the data can and cannot tell:**

- **A sitting member's chamber** is the roster's. **A former member's** is the
  one they last sat in. All 24 on dry run 7 are in `former.json` under one
  chamber, and none is also sitting.
- **A sitting or former member with no row** gets no word rather than a guess.
  A check holds that. None of the 405 is like that.
- **NEW means the file links them to nobody.** The rosters start in 1999, so
  someone who sat only before 1999 would read NEW, as would a member the
  name rule could not match.
  - On dry run 7 the review ran the matching rule again and found nobody
    unlinked.
  - It also checked each of the 168 by name against both rosters. One name
    matched: Rich Green, former Sen. Richard Green, whom the corrections file
    already records as a different person.

**5. The Senate in By county** is grouped by county the way the Legislators
tab's By county groups it. A Senate district crosses county lines and the
results file names no county. So each district's members-elect go under the
county the Legislators tab lists that district under: the roster's county for
the senator who holds it now. A district nobody holds would go under "Not on
file", last. On dry run 7 the two tabs show the same eight counties with the
same counts: Belknap 2, Carroll 1, Cheshire 3, Grafton 2, Hillsborough 6,
Merrimack 2, Rockingham 6, Strafford 2.

Both tabs read the same field: each senator's county in `legislators.json`.
The rule is not shared code: the Legislators view is drawn by its own builder
from that field. A check holds this tab to the rule on its fixture: district
8 goes under its senator's roster county, and district 9, which nobody holds,
under "Not on file".

**6. The bar on a phone.** "Who holds the seats" and "Who won the seats" now
draw each chamber's bar on a phone too, 10px high, above that chamber's one
line of counts. Before, the phone had the line and no bar. From 621px up,
nothing changes: the bars, the legends and the threshold sentences are as
they were.

## For Alice to decide

- **The ring.** A small ring per chamber was mocked at 375 (scratch only, not
  on the branch; `d-*-donut-375-*`, beside the bar's `d-*-bar-375-*`). It
  reads, but not clearly better, so the bar is built:
  - The one-seat slices (1 I, 1 I/D, 1 R/D) are too thin to see in either.
  - The ring loses the bar's hatching for "not final".
  - It takes width from the line of counts beside it.
- **The House line on a phone is still two lines on Members-Elect** at 390px
  and below: "House 279 D · 99 R · 1 I · 1 I/D · 1 R/D ·" / "19 not final". It
  breaks between counts. The options are unchanged from the last batch:
  - fold the two cross-nominations into one count;
  - say "3 other";
  - keep it.
- **13 chips take two lines at 390** whose Legislators chip takes one, for
  example "Rep.-elect Mary Ngwanda Georges (D - Hills 23)". The word is not the
  cause. "-elect" adds six characters, and the file has the name as the
  Secretary of State printed it ("Mary Ngwanda Georges", "Catherine A.
  Rombeau") where the roster has "Mary Georges", "Catherine Rombeau".
  - Using the roster's name for a sitting member would bring 13 down to 7
    (27 down to 12 at 375). The other 7 are "-elect" alone.
  - The branch keeps the Secretary of State's names.
- **On a phone the word is beside some chips and under others** (`r1-after-390-light`):
  beside where both fit on the line, as for most NEW, and under where they
  don't, as for most RETURNING. Always under on a phone would be even, and a
  line taller for each of the 67 now beside.
- **Two columns, not three.** On a desktop the lists have two columns where
  the Legislators tab has three, so that each word fits beside its chip.
  - The page is shorter: By last name is 18,535px tall at 1280, against
    26,595.
  - The fourth party column (Independent, 1) still starts under the longest
    column, as it did before.
- **The Senate's county** is the roster's, as the Legislators tab has it. For
  5 of the 24 districts that is not the county most of the district's towns
  are in. The same choice is on both tabs.

## Spanish (drafts)

- **The words:** Reelegido/a, Nuevo distrito, Nueva cámara, Nuevo/a.
  Reelegido/a ("elected again") is right for a member re-elected to their seat
  and for a former one elected back. The review found that the old "Regresa"
  told 206 sitting members they were coming back.
- **Not final:** "19 escaños por definir, en 16 distritos" ("1 escaño por
  definir"; "2 escaños por definir, en un distrito"); "Se pidió un recuento en
  cada uno." ("Se pidió un recuento.").
- **The views:** Por apellido, Por condado.
- **Removed:** three entries only By district asked for (State House, State
  Senate, "{n} seat"), and the Spanish term list's exception for the first.

## The shots

Dry run 7 as served ("before"), and with this branch applied ("after").
Playwright served the pages from disk; nothing else was fetched but the
deployment's own scripts and data and the fonts.

- **The Members-Elect panel** is this branch's
  `officials_tabs.members_elect`, run on dry run 7's own `members_elect.json`,
  `legislators.json` and `former.json`, its links as the build writes them.
- **The two inline scripts** (the strips and the addresses) are this
  branch's.
- **Each chamber's line** is moved into its own block, as this branch's
  `static_bar` writes it.
- **The tab and the panel** are moved after Legislators.
- **The stylesheet** is this branch's as published. The other files are dry
  run 7's, which this branch does not change.

| Shot | What |
|---|---|
| `t1-{before,after}-{1280,390}-{light,dark}` | The tab strip (item 2). |
| `l1-{before,after}-{1280,390}-{light,dark}` | Legislators, Who holds the seats (item 6). |
| `l2-{before,after}-{1280,390}-light` | The same, in Spanish. |
| `m1-{before,after}-{1280,390}-{light,dark}` | Members-Elect's top: Who won the seats, the not-final fold, the strip (items 1, 6). |
| `m2-{before,after}-{1280,390}-light` | The same, in Spanish. |
| `n1-after-{1280-light,390-light,390-dark}`, `n2-after-390-light` | The not-final fold opened; `n2` in Spanish. |
| `r1-before-{1280,390}-light` | By district's Belknap District 6, as it was. |
| `r1-after-{1280,390}-light` | By county's Belknap: its members, then the not-final line. |
| `c1-{before,after}-{1280,390}-{light,dark}`, `c1-*-375-light` | By last name, the Senate: the chip and the word (items 3, 4). |
| `c2-{before,after}-{1280,375}-light` | The same, in Spanish. |
| `c3-{before,after}-{1280,390}-{light,dark}`, `c3-*-1024-light` | A House member elected to another House district: NEW DISTRICT. At 1024 the chips wrapped before. |
| `s1-{before,after}-{1280,390}-{light,dark}` | By county, the Senate: before by district, after by county with Cheshire opened (Creighton, NEW CHAMBER) (item 5). |
| `s2-after-{1280,390}-light` | The Legislators tab's By county Senate, for comparison: the same counties and counts. |
| `s3-after-390-light` | Members-Elect By county's Cheshire, in Spanish. |
| `d-members-elect-{bar,donut}-375-light`, `d-legislators-{bar,donut}-375-dark` | The ring mock beside the bar. |

## Measured on the after pages

- **Sideways scroll: none from this branch.**
  - **What was measured:** every width from 320 to 1280px in 10px steps,
    English and Spanish. At each width, three places: the Legislators tab's
    top, By last name, and By county with every county open.
  - **The result:** 582 measurements, with no chip, word or line past its box.
  - **Seven, in Spanish, scroll sideways,** at 320–350 and 490–510px. These
    are the Presiding Officers' labels on the Legislators tab. Dry run 7 does
    the same: it is the pre-existing case already set for 11 November.
- **The word is never inside the chip.** That holds for all 405 at every
  width in both languages; on dry run 7 every one was inside.
- **Addresses** (1280, after):

| Address | Lands on | Dry run 7 |
|---|---|---|
| `#members-elect`, `#pane-elast`, `#of-elect-senate`, `#of-elect-house` | Members-Elect, By last name | the same |
| `#pane-ecounty` | Members-Elect, By county | By last name |
| `#pane-edist`, `#tab-edist` | By county, the address rewritten to `#pane-ecounty` | By last name |
| `#of-eld-senate`, `#of-eld-house` | By county, at the chamber's heading | By last name |
| `#of-eld-senate` followed from Legislators | Members-Elect, By county, at the heading | By last name |
| `#of-eld-house`, then By last name picked, then reload | By last name, where the reader was | (no such view) |
| `#pane-seat`, then By last name picked, then reload | By last name, where the reader was | By last name |

- **Once the tab has gone (2 December),** each of these addresses opens
  Legislators: `#pane-edist`, `#of-eld-senate`, `#of-eld-house`, `#pane-elast`
  and `#pane-ecounty`.
- **The page is lighter.** /officials goes from 786 to 700 KB (109 → 100 KB
  gzipped), and /es/officials from 800 to 712 KB, with one view fewer.

## The review

Four reviewers each read one side of the change:

- the words against dry run 7's data;
- the strips' and addresses' script;
- the stylesheet;
- the checks.

A skeptic then tried to reproduce each finding on the real data. Eleven
findings; six held up, five did not.

**Fixed on this branch:**

- **Most words went under the chip on a desktop (should-fix).** That is the
  column change under item 3.
- **"Regresa" (minor).** It told 206 sitting members they were coming back;
  the draft is now Reelegido/a.
- **A reload or Back reopened the wrong view (minor).** After arriving at an
  address that names a view (`#of-eld-house`, `#pane-seat`) and picking
  another, a reload reopened the first view, scrolled to a place in the
  other list.
  - **The fix:** picking a view now renames the address to that view, with
    no new history entry, but only where the address named another view.
  - **Checked:** in Chromium the reload now keeps the view picked and its
    place. Every other address behaves as on dry run 7.
- **Three gaps in the checks**, each closed and proved with a mutant:
  - the view's own address (`#pane-ecounty`) through the strips' script;
  - the bar hidden on a phone by height or visibility;
  - three retired addresses (`#pane-elast`, `#pane-ecounty`, `#of-eld-house`)
    once the tab has gone.

**Not real, or not this branch's:**

- **"NEW also covers winners the rule could not link."** The rule leaves
  nobody unlinked on dry run 7. What NEW rests on is said under item 4.
- **"#tab-ecounty is not followed."** No address names a strip's own button,
  on dry run 7 or here. The Legislators strip's buttons behave the same.
- **A comment on former members' chambers.** It draws nothing wrong.
- **Two findings made against a stale copy of the stylesheet**, or already
  fixed.

## Mutation testing

Each of 24 mutants breaks one thing the branch does; 23 turn a named check
red:

- RETURNING given to a member who changed chamber, or to every former
  member, or to a member elected to another district;
- no word where the rows cannot say;
- the word inside the chip, or not in capitals;
- the wider columns, in either view;
- the Senate by district again;
- the not-final list, and By county's not-final line;
- the phone's bar hidden, with no height, or invisible;
- the phone's line outside its block;
- the tab after Federal;
- each address case:
  - the By district alias and the retired addresses;
  - the view an address names, on arrival and on a hash change;
  - the view's own id;
  - the address renamed when a view is picked.

The one that lives sets a list row to `display:block`. The word still follows
the chip and still goes under it where the two don't fit, so the page looks
the same.

## Checks

- `preflight --code` on c1cf71d7, the branch's code as it stands (later
  commits add this README and its shots only): 995 passed, 0 failed, 9
  skipped. The 9 need data a cloud session does not have.
- Stamps: `app.css` .355, `build_pages.py` .265, `officials_tabs.py` .12,
  `preflight.py` .800, each one past aa4d8582. `inventory.py`: every file
  matches.
