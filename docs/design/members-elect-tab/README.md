# Members-Elect like Legislators, and the seats at the top (8 November 2026)

Alice's walk of 7 November 2026, items A, B and C, for Sunday's dry run. The
branches:

| Item | Branch | What it holds |
|---|---|---|
| A | `fix/presiding-line` fb7d3e01 | the sentence under the Presiding Officers removed (its own README: `docs/design/presiding-line/`) |
| B, C | `feat/members-elect-tab` | A, then the Members-Elect tab and the seat totals |
| D | `feat/map-party-totals` | A, B and C merged in, then the map's line (its own README: `docs/design/map-party-totals/`) |

## What a reader sees

**A. The Presiding Officers** are their three chips and nothing under them, in
English and Spanish. Each chip's role says the office.

**C. Who holds the seats** is at the top of the Legislators tab, under the
Presiding Officers and over the roster; it was at the bottom, 24,799px down
on a phone. On a phone each chamber is one line, from the bar's own counts:

    Senate 16 R · 8 D
    House 212 R · 169 D · 1 I · 18 vacant

The bars, their legends and the threshold sentences ("three fifths ... 230 of
the 382") show from 621px up; on a phone they are not drawn. The vacancies
fold ("18 vacant House seats across 18 districts") stays in both.

**B. The Members-Elect tab** opens with its sentence, then **Who won the
seats** in the same form (per chamber: the parties largest first, the
cross-nominated by their letters, the seats not final apart, and any seat with
nobody on file apart), then the members-elect three ways under a strip like
the Legislators tab's:

- **By last name** (shown first): Senate and House apart, each under its count
  ("House — 381"), a column per party, largest first, A to Z by surname and
  then given name. A linked member's surname is the roster's own (Rebecca
  Perkins Kwoka is under P, as on the Legislators tab); anyone else's is the
  name's last word, a "Jr." aside.
- **By county**: the House as the Legislators tab's By county, each county shut
  until opened, its members by district and then name. The Senate is listed
  by district, because a Senate race in the file names no county.
- **By district**: each race whole, as the tab was: its seats, its
  members-elect, and "Result not final — a recount was requested" or "No
  member-elect on file" where they apply.

Each member-elect is the Legislators tab's person chip with a title, party and
district, and a word:

| The file says | The word | Example |
|---|---|---|
| sitting, re-elected to the seat they hold (`own`) | **Re-elected** | Rep.-elect Charles Foote (R - Rock 13) |
| sitting, elected to another seat | **New seat** (proposed) | Sen.-elect Jim Creighton (R - SD8), who holds Hills 30 |
| former | **Returning** | Sen.-elect Shannon E. Chandley (D - SD11) |
| new | **New** | Rep.-elect Kristine Trow (D - Rock 13) |

Seven members-elect carry **New seat** on dry run 6: two representatives
elected to the Senate (Creighton, Telerski) and five elected to another House
district. A member-elect is linked only where the file links them, and there
is no contact detail.

**The 19 seats not final** (16 districts):

- **By last name** lists people, so it says once under the House heading:
  "Result not final for 19 seats in 16 districts — a recount was requested in
  each. By county and By district name them."
- **By county**: the county's summary counts them (Belknap's reads "Belknap",
  "17", then "1 not final" in small type) and a line under its members names
  them ("Result not final in District 6 — a recount was requested").
- **By district**: each district says it, as before.
- **Who won the seats**: "381 of 400 seats elected, 19 not final", a hatched
  segment of the bar, and "19 not final" on the phone's line.

"Your rep" and "Your senator" (a saved town) still mark only a member
re-elected to their own seat, in all three views. With Derry saved, Foote and
Regina Birdsell are marked; with Antrim saved, Creighton is not.

## For Alice to decide

- **The word for a sitting member elected to another seat.** "New seat" is the
  proposal. "Returning" would read as a former member coming back. Another
  option is the seat they hold now, e.g. "Now Hills 30".
- **On a phone, the members-elect House line takes two lines:**

      House 279 D · 99 R · 1 I · 1 I/D · 1 R/D ·
      19 not final

  - **Where.** In English, from 320 to 390px (one line from 412px). In
    Spanish, at every phone width. The Senate's line, and both of the
    Legislators tab's, are one line even at 320px.
  - **How it breaks.** Between counts, never inside one.
  - **Options, measured** (a 390px phone leaves 366px for the line):
    - **Fold the two cross-nominations into one count:** "2 R/D·I/D" is
      362px. It fits at 390 in English only.
    - **Say "3 other"** for the Independent and the two cross-nominated: 318px.
      It fits everywhere, and the bar and legend on a wider screen still
      name each one.
    - **Keep the two lines.**
- **The threshold sentences are not on a phone.** If they should be, they
  could go under a fold.
- **The Senate in By county** is by district, as above.
- **The page is heavier**: /officials is 616 KB → 805 KB, or 92.5 → 111.7 KB
  gzipped, for 405 members-elect drawn three times. The tab and all of this
  leave the page on 2 December.
- **`#of-elect-senate` and `#of-elect-house`** now name the chamber headings
  in By last name, the view shown first, so an old link still lands on them.

## Spanish (drafts)

Rep. electo/a, Sen. electo/a; Reelegido/a, Nuevo escaño, Regresa, Nuevo/a;
Quién ganó los escaños; Por apellido, Por condado, Por distrito; "19 por
definir"; "Senado 16 R · 8 D", "Cámara 212 R · 169 D · 1 I · 18 vacantes".

## The shots

Dry run 6 (https://7c76e0a0.graniterecord.pages.dev) as served, with
`fix/members-elect-polish` 068ed8b0 applied ("before") and with this branch on
top of it ("after"). Playwright served the pages and the stylesheet and
scripts in place.

- The Members-Elect panel is this branch's `officials_tabs.members_elect`, run
  on dry run 6's own `members_elect.json`, `legislators.json` and
  `former.json`.
- The Presiding Officers are this branch's `presiding`, run on its
  `officers.json`.
- "Who holds the seats" is the served block moved to the top, with each phone
  line taken from the served bar's own counts by `short_bar`'s rule.
- The stylesheet and `find.js` are as this branch's build publishes them.

| Shot | What |
|---|---|
| `l1-{before,after}-{1280,390}-{light,dark}` | The Legislators tab's top: A and C. |
| `l2-{before,after}-{1280,390}-light` | The same, in Spanish. |
| `m1-{before,after}-{1280,390}-{light,dark}` | The Members-Elect tab's top: the totals, the strip and By last name. |
| `m4-{before,after}-{1280,390}-light` | The same, in Spanish. |
| `m2-after-{1280-light,390-light,390-dark}` | By county, Belknap opened, with its seat not final. |
| `m3-after-{1280,390}-light` | By district, Rockingham 12 to 14, with seats not final. |
| `m5-after-320-light` | Spanish By last name at 320px, the House's first Democrats, most with no page: the worst case the review found. |
| `m6-after-{600,900}-light` | Spanish By county, the Senate beside its districts: where a word ran past the chip and the page. |
| `y1-after-{1280,390}-light` | Derry saved: "Your rep" on Foote alone. |
| `y2-after-1280-light` | Antrim saved: Creighton unmarked. |

Measured on the after pages:

- **Sideways scroll and overruns: none.** Every width from 320 to 1280px in
  10px steps was measured, in each of the three views, in English and
  Spanish, with every county open. That is 582 measurements; each had no
  sideways scroll and no part of a chip past its border.
- **Unlinked names: no squeeze.** No member-elect with no page has their name
  pressed into a narrow column. None runs to more than two lines at 320,
  390, 600, 900 or 1280.
- **The strip** opens on By last name, and each strip switches only its own
  panes.

## The review

Four reviewers each read one side of this (what is drawn; accessibility and
the script; layout and dark mode; the checks, the Spanish and the merge). A
skeptic then tried to reproduce each finding on the real data. Eleven were
confirmed.

**Fixed on this branch:**

- **Squeezed names (should-fix).** The 168 members-elect with no page had
  their name drawn one word to a line beside the tag ("Rep. / electo/a / Tom
  / Ahlborn- / Hsu", Spanish, 320px).
- **Words past the edge (should-fix).** A chip's word ran past its border,
  and in Spanish By county past the page's edge, at 590–640 and 900–910px.
  - **The fix for both:** in this tab's lists a chip's parts wrap inside the
    chip. The shared chip is unchanged.
- **Heading levels.** By district opened at h3, under "Who won the seats"
  in the outline. It now opens at h2, as the other views do.
- **No JavaScript.** Without it, both strips were three buttons that did
  nothing. Each strip is now written hidden and shown by its script, as the
  town pages' strip is.
- **The checks.** Three gaps in the new checks are closed:
  - "Under the presiding officers" was never tested, because the fixture
    draws none.
  - The order by county had no county with two districts.
  - The Spanish sweep missed capitalised words and attributes.

**Not fixed, pre-existing and live today (for 11 November):**

- **Legislators tab, By county, sideways scroll.** The page scrolls sideways
  at 840–1220px, by up to 108px: a long chip overruns its 250px cell. The
  verified fix is this branch's cell treatment, plus the tag in its own span
  in the script that draws that view.
- **Spanish Presiding Officers, sideways scroll.** The labels push the page
  sideways at 320–350 and 490–510px. The verified fix is one rule:
  `.ofpres .mchip{flex-wrap:wrap}`.

**For Alice:** the members-elect House line on a phone takes two lines
(above).

## Mutation testing

Each of the 29 mutants breaks one thing the branch does, and each turns a
named check red:

- the surname rules;
- the four words;
- the title;
- links;
- "Your rep";
- both strips, their script, and the hidden strip;
- the totals' place and the phone's lines and CSS;
- each view's "not final";
- the addresses;
- the order by county;
- the heading levels;
- the chips' wrapping;
- the Spanish.
