# Cohesion batch: what changed, with screenshots (for 11 November)

The branch is `cohesion`, cut from dev c9a5964. It carries the manager's share of the
cohesion audit (`design/cohesion-audit` 03a24ee, `docs/design/cohesion-audit/REPORT.md`).

- **In this batch:** the BROKEN items, the S-effort top-ten items, and the term years (I-2).
- **Not yet:** the search box (I-7) and the rest of the heading levels (I-1 beyond B-1).

One commit per item, then two commits from the two-lens review and two that finish the
term years.

## How the shots were made

Each shot is `<item>-<view>-<before|after>-<390|1280>-<light|dark>.png`.

- **Before** is dev's file, routed into the preview's own page. **After** is the branch's.
- **Built-HTML changes:** where a change is in built HTML rather than a script or a
  stylesheet, "after" rewrites that markup the way the branch's builder now writes it.
  That covers a guide's times, the home page's webinar line and play buttons, and a Learn
  table's box. Each section says which.
- **Requests:** every request to the General Court's servers was blocked.
- **Exception:** the Bills page itself does not load under dev's or the branch's scripts
  on the preview, whose data is older than dev, so I-2 is measured rather than shot.

## B-5 Citations: APA and Chicago say "October 30, 2026" (`b5-cite-*`)

| Form | Before | After |
|---|---|---|
| APA | "Retrieved 30 Oct. 2026, from …" | "Retrieved October 30, 2026, from …" |
| Chicago | "Accessed 30 Oct. 2026." | "Accessed October 30, 2026." |

- **MLA and BibTeX** keep "30 Oct. 2026".
- **The date's source:** the build writes the date with `shell.cite_day_full` and the
  browser with `citeDayFull`, both using the site's own full date.
- **Fixed in review:** the Bills list's copy of a bill's citations now keeps the full date
  too.

## B-6 A bill suffix's glossary button is a 24px target (`b6-suffix-*`)

- **The fix:** a transparent `::after`, at least 24px each way, is laid over the button.
  The letter and its neighbours do not move.
- **Measured at 390:** a tap 11px left, right, above or below the "A" of HB 2-FN-A-LOCAL
  lands on it in all four directions. Before, only two of the four landed.

## I-3 Times as `clock()` writes them (`i3-webinar-*`, `i3-guide-vote-*`)

- **The guides:** twelve lines of the guides' own words now read "8:30 AM" and "5:00 PM".
- **The home page:** the webinar line now reads "6:30 PM".
- **Spanish:** the Spanish drafts read "8:30 a. m.".
- **Kept as written:** a claim's words and the House calendar lines a guide quotes keep
  their source's "a.m.".
- **The hours check:** `guides.CLOCK`, which holds every hour a guide prints to its claims,
  reads both forms. Without that, the new times would have gone unchecked. 42 hours are
  read, each on a claim.

## I-6 One look for a switch (`i6-calendar-chamber-*`, `i6-map-rows-*`, `i6-versions-*`, `i6-vmode-*`)

- **The look:** the chosen option is solid pine in an edged, square group, as the roster's
  and the Calendar's List/Week/Day switches already were.
- **Where it now applies:**
  - the map's two rows;
  - the Calendar's chamber row, which were the site's only round buttons;
  - a bill's versions and "What changed / Full text".
- **Fixed in review:**
  - The chamber row now fills the Calendar's side column on one row
    (`i6-calendar-chamber-fixed-*`). At 12px a side, "Senate" wrapped to a row of its own.
  - In forced colours, the chosen option is filled with Highlight, so a focused option is
    not mistaken for it.
- **Not changed:** Resources' tabs stay a three-column grid on a phone. That grid shows
  every tab at once, where the other tab rows scroll.

## B-1 A heading under a section is smaller than the section's own (`b1-*`)

| Page | Before (h2 / h3) | After |
|---|---|---|
| A guide's Step by Step | 19px / 20px | 19px / 18px serif |
| Learn | 19px / 19px | 19px / 18px sans |
| /data | 19px / 19px | 19px / 18px sans |

- **Why Learn and /data use the sans:** the review found 18px serif over 18px serif text
  read as a bold first sentence.

## B-2 A Learn table that scrolls can be reached by keyboard (`b2-table-*`)

- **Measured at 390 on By the Numbers:**
  - before: 15 boxes wider than the screen, 0 reachable by Tab, 0 named;
  - after: all 15 reachable and named.
- **How:**
  - `build_civics.section` gives every Learn and guide table box `data-scrollstop` and a
    name: its caption, or its section's heading with the nearest heading or fold above it.
  - app.js's `scrollStops` makes the box a region and a Tab stop while it scrolls, and
    only then.
  - It measures again when a fold opens.
- **Kept as it was:** the edge that shows a box scrolls stays the faint one. It takes
  `--scrolledge` once the R2 batch is in dev.

## I-11 One word for one meaning (`i11-home-play-*`)

- **A bill that ended:** a committee meeting's card now says "Died:", as the Bills chip
  does. It said "Killed:".
- **The home page's players:** they say "Play the recording", as every other player does.
  Their accessible names now begin with those same words (fixed in review, WCAG 2.5.3).
- **A recording with no marked moment:** it says "Exact moments not found.", after a bill's
  "(exact moment not found)".
- **Kept as it was:** Learn's worked example "Killed: HB 66" keeps its word, because its
  Spanish entry is keyed by it.

## I-2 A term's years: "2025–2026"

- **The helpers:** `termWords` in components.js and `term_words` in components.py write a
  two-year term with an en dash. They return anything else as they received it, such as
  "2027-requests".
- **Where they are used:** every builder and app.js ask them for what a reader sees. A
  term's key, its address, a file's name and a citation's URL keep the hyphen.
- **Measured on the preview with the branch's scripts:**

  | Page | Hyphenated terms before | After |
  |---|---|---|
  | A committee's page | 39 | 1 |
  | A bill's page | 20 | 1 |

  The one left on each page is built HTML, which the check below covers.
- **The new check:** `_terms_with_a_dash` reads every page the fixture builds, its text and
  its spoken names, and allows a hyphenated term only inside an address or a file's name.
