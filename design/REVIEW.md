# The site as it renders, 15 September

A visual audit of the live pages, not of the stylesheet. Nine pages were built and
photographed at 360, 768 and 1440 pixels in both themes -- the home page, bill search,
a bill, a legislator, a committee, the Learn hub, a Learn page, the roster and the data
page -- and every finding below is something visible in one of those pictures or
counted in the files. It is written against `DESIGN.md`, which is the standing brief,
and `design/BRIEF.md`, which is the outside proposal.

Ordered the way the person ordered the work on the 15th: things that mislead or hide
data first, then the inconsistencies, then taste. Nothing here is built until it is
agreed.

---

## 1. Small defects a reader meets

**"press / to search" on a phone.** The keyboard hint sits under the search box at
every width, including 360, where there is no key to press. Bill search and every
record page carry it.

**"2,234 of 2,234 bills in the 2025-2026 term."** The count is drawn before any filter
narrows anything, so its first reading is a number that cannot be wrong and does not
inform. It should appear when a filter or a search is on, and say nothing otherwise.

**Double hyphens in the Learn prose.** `--` is printed where an em dash is meant, 5
times on the Learn hub and 54 times across the eleven pages: "The Council -- five
members, elected by district -- approves contracts". Nowhere else on the site does
this; it is Learn copy written in the source's own shorthand and never converted.

**A bill's tabs wrap to three rows on a phone.** Summary, Bill Text, Votes, Videos,
Reports, Sponsors and Documents stack into three lines above the record, so on a 360px
screen the tab strip is 120 pixels of chrome. `design/header.html` shows the
alternative: one row that scrolls sideways, counts kept, with a fade at the edge to
show there is more. This is the tab navigation the person asked for.

---

## 2. Where the pages disagree with each other

**Three different left edges.** At 1440 the record pages begin at x=155, the data page
at x=270, and the Learn hub is centred with its first character at x=440. `DESIGN.md`
already says "one left edge"; three pages read as three sites. This is the single most
visible inconsistency in the set and the cheapest to fix.

**Two stylesheets.** Record pages (bill search, bills, legislators, committees) are
styled by `app.css`; the home page, roster, Learn, town and data pages by `style.css`,
which `build_pages.py` writes. The palette and one shared region are read out of
`app.css` at build time, so colours agree, but the rest is separate: 216 font-size
declarations in one file and 62 in the other, with no shared scale. Every rule below
has to be applied twice until this is one source.

**Eleven font sizes in `app.css` alone**, from 10px to 32px (14px 102 times, 12px 49,
16px 26, 13px 13, 15px 9, 19px 7, 11px 4, 24px 2, 28px 2, 10px and 32px once each),
and more in `style.css`. 13px and 14px, 15px and 16px do not read as different
decisions; they read as different days.

**Spacing has no tokens at all.** Radii and colours do (`--r-out`, `--r-in`,
`--r-pill`, 533 `var()` uses in `app.css`; only 4 colour literals outside the token
block, all on the video placeholder, and those four are duplicated in `build_pages.py`).
Padding and margins are typed in per rule, which is why cards, panels and list rows
each sit on their own rhythm.

**Two ways of saying "you are here".** The current item in the site nav is a box with a
border; the current tab on a bill or a member page is an underline. The nav's box is
also the exact shape of the theme button beside it, so the state you are in looks like
a control you can press. One treatment, everywhere, and the underline is the one that
does not collide with a control.

**The accent does two jobs.** The same green family marks links and fills status pills
("Signed into law", "Adopted by the House"), so a pill reads as something to click. On
a committee page the member chips add a third use: party-tinted, underlined, and
clickable. Status wants a hue of its own, quieter than the link colour.

**Detail pages carry different chrome.** A bill page keeps the search band at the top;
a legislator and a committee page do not. Whatever the rule is, it is not being applied
to all three.

**Prose stops at 34em inside a 1180px page.** On the committee page "What it does" ends
at x=700 with the right half of the screen empty; the data page does the same. A
reading measure is right for prose, but the person has said an empty right half reads
as broken, so those pages want a layout that uses the width -- a second column, or a
narrower page frame for prose-led pages.

---

## 3. Settled, and not to be revisited here

- **The home page keeps its large logo and the slogan under it**, with the small brand
  in the masthead. `BRIEF.md`'s "never duplicated in a hero" is overruled.
- **The typefaces stay Public Sans and Newsreader** unless the person asks for the
  change; the mockups' Playfair Display and IBM Plex are a different decision from a
  tidy, and the wordmark is already drawn.
- **The theme follows the reader's system** until they choose, with no Auto state.
- **ALL-CAPS labels and the external-link arrow stay**; `DESIGN.md` wants them.

---

## 4. The order to do it in

One rule per commit, applied to both stylesheets in the same commit, with the nine
pages re-photographed at three widths afterwards and compared with the set taken today.

1. **One container.** Same left edge and same maximum width on every page.
2. **One "you are here".** Underline for state; a border means a control.
3. **One stylesheet.** Make `style.css` a generated view of `app.css` rather than a
   second hand-kept file, then move the last four colour literals into tokens and add
   the preflight check that fails on a new one. `BRIEF.md` is right that this is the
   only part of the pass that survives it.
4. **A type scale.** Seven sizes as tokens, every declaration pointing at one.
5. **Spacing tokens**, applied to cards, panels and rows.
6. **Tabs that scroll on a phone**, counts kept, edge fade.
7. **The count when it counts**, and no keyboard hint on a touch device.
8. **Status gets its own hue**, and the accent means interactive.
9. **Em dashes in the Learn prose.**

Items 1, 2, 6, 7 and 9 are visible to a reader. Items 3, 4 and 5 are what stop the
inconsistency coming back, and they are invisible if done correctly -- the screenshots
before and after should be identical, and a difference is a bug in the extraction.
