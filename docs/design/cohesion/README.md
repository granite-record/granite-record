# Cohesion batch: what changed, with screenshots (for 11 November)

The branch is `cohesion`, cut from dev c9a5964. It carries the manager's share of the
cohesion audit (`design/cohesion-audit` 03a24ee, `docs/design/cohesion-audit/REPORT.md`).

- **In this batch:** the BROKEN items, the S-effort top-ten items, and the term years (I-2).
- **Part 2, below:** the search box (I-7) and the rest of the heading levels (I-1 beyond B-1).
  Its "before" is part 1's head, a5e56494.

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

# Part 2: one search box (I-7) and one look per heading level (I-1)

Four commits on top of part 1, each with a preflight check. The shots follow the same
naming. "Before" is part 1's head (a5e56494), and "after" is this branch.

## I-7 One search box (`i7-*`)

| Box | Before | After |
|---|---|---|
| Officials (`#lq`) | 52px, 20px text | 44px, 16px |
| /search (`#resq`) | 52px, 20px text | 44px, 16px |
| A member's Votes | grey ground; 35px at 1280 | white, 44px |
| Calendar (`#wkfind`, `#cpfind`) | 40px | 44px |
| Bills and a bill's page (`#q`) | 42px, on the page's grey | 44px, white |

- **The Bills page's term menu** (`#year`) is 44px too, so it lines up with the box beside
  it.
- **Hints, the manager's option A:**
  - the owner's three bill hints stay as they are;
  - a member's Votes box now says "Bill number or title words" (it said "HB 1442, or
    words");
  - the Calendar's box now says "Bill number or committee" (it said "HB 1234, or
    Judiciary").
  - Neither box has a Spanish layer.
- **The search button** inside the box is centred on a phone too. The pages' 44px least
  height for a button had stretched it 5px past the box's foot (fixed in review).
- **The check:** `_one_search_box`.

## I-1 A bill's tabs head their sections one way (`i1-bill-*`)

| Tab | Before | After |
|---|---|---|
| Summary, Votes | 19px serif, Title Case | unchanged |
| Reports | 20px serif capitals ("HOUSE JUDICIARY COMMITTEE") | 19px serif, "House Judiciary Committee" |
| Sponsors | 20px capitals, bare count | 19px serif, count in small sans |
| Documents | h3, 14px sans capitals, no h2 | h2, 19px serif |
| Related | 16px sans, sentence case | 19px serif, Title Case |
| Bill Text | "BILL TEXT" in 20px capitals | "Bill Text", 19px serif |

- **The class:** `.sech` draws all of these, as Summary's `.w4h` and a vote's `.rcq`
  already did.
- **The capital label** stays for a group inside a section: THE BILL, FISCAL IMPACT and
  HOW IT GOT HERE under the bill text. Under "Bill Text" these labels are now 16px, so
  they no longer outrank the heading above them (fixed in review).
- **A report's committee:** a report is now headed with its committee's name in Title Case,
  part by part, so a name stored in capitals reads in Title Case. "Committee" is added only
  where the name lacks it, so "House Joint Committee on Address" no longer gets a second
  "Committee" (fixed in review).
- **The heading map:** the map beside the tokens in app.css names this level ("pane").
- **The check:** `_bill_panes_one_heading` holds the three rules together. It also reads
  every h2 the pane renderers write, and draws Sponsors and Documents in node.

## I-1 The rest (`i1-home-*`, `i1-committees-*`)

- **Home:** "Coming up" was typed in sentence case. Capitals hid it at 1280, and a phone
  showed it. It is now "Coming Up", in English and in es.json's English. The Spanish is
  unchanged.
- **Titles in Title Case:** "Calendars and Journals of the General Court" and "The Whole
  Record, as Lists".
- **/search:** its group names are in Title Case ("Towns and Wards", "Statutory and Study
  Committees", "Former Senators"…), to match "How-To Guides".
- **/committees:** the statutory and study fold's heading takes the page's other section
  headings' look, 20px serif capitals. It was 16px sans in pine. The caret and the box
  still show that it opens.
- **A Laws chapter without parts:** it went from its h1 to an h3 for every section. Its
  sections are now h2, and h3 only under a part's h2, as the Constitution tab's articles
  already were. The look is unchanged. The check is `_laws_chapter_outline`.

## Left as it was

- **About's headings** stay at 24px, stacked. That size is the rule for every plain prose
  page (About, Officials, /search, 404), and the audit counts it as a section heading.
  Moving About into /data's left-margin layout would change its width and its body text.
  The manager decided to leave it (30 October).
- **The Hearings tab's hearing-report fold** ("Who took a position") sits inside a
  sitting's fold rather than opening the pane, so it is unchanged (the manager, 30
  October).
- **A Laws chapter's box of pending bills** ("Passed, not yet in effect") keeps its 16px
  sans headings in sentence case. It is a box beside the chapter's text, and was not part
  of the audit's row.
- **The search results' own rows** for the site's pages ("The whole record, as lists",
  "The data, as tables") stay as written. They are link labels in a list, not headings.
