# Action panes: polish block (6 November 2026)

On branch `fix/action-panes` at dc8404f, on top of 655438f.

## What changed

- **A short pane on a phone covers the buttons beneath it.**
  - On HB 1123 at 390, Testify's pane is one sentence long, and the bottom 8px of "Report a problem" showed under it (33px at 700).
  - A phone's pane now always reaches at least the bottom of the actions.
- **High-contrast mode keeps the band.**
  - On a phone, a strip of page background hides the tops of the next row's buttons in the gap between the button and its pane.
  - Windows high-contrast mode drops the pane's shadow, which drew that strip.
  - In that mode only, the open button now draws the strip itself, in the mode's own background colour.
  - See `bill-testify-390-forced-*`.
- **The facts follow the title (cohesion audit P-2).**
  - On a bill at 1280, PRIME SPONSOR sat 110px under the title, while a member's facts sat 74px under theirs. The column of five buttons beside them was stretching the rows.
  - The column's extra height now sits in an empty row under the facts.
  - Title to facts is now 53px on a bill, a member page and a session day, at 1280 and 1024.
  - The rail under the head has not moved.
  - The phone layout is unchanged.
- **No lone full stop in Cite (cohesion audit P-4).**
  - Before, on HB 1123, the Chicago form left "." alone on the last line at 385–388px, and BibTeX left "}," alone at 445–451px.
  - The address now offers a break after each slash. Its last part, with the full stop after it, moves to the next line as one piece.
  - Copied citations are character for character the same.
  - The calendar renames the citation as a reader moves between weeks, and redraws the address the same way.

## The 24px sideways scroll: not a site bug

The 124px scroll at 1280 came from how it was measured. The test raised the page's own text size to 24px. That makes the text bigger but leaves the layout's width breakpoints where they were, so the full desktop navigation row was laid out with 24px words.

A reader who chooses large text sets it in the browser, and the breakpoints follow that setting. With Chrome's own default font size at 24px nothing scrolls sideways:
- on a bill, a member page, a committee page and a session day;
- at 360, 390, 1024, 1280 and 1440;
- with every pane closed, and with each pane opened (18 openings).

Firefox's "zoom text only" moves these breakpoints the same way. The earlier note in `../nub/README.md` that said otherwise is wrong.

## Shots

Every shot has a `-before.png` version (655438f) and an `-after.png` version (this branch now):
- `bill-*` is HB 1123; `sessionday-*` is the House, 21 May 2026; `member-*` is Abigail Rooney.
- `*-head-*`: the record head with every pane closed, at 390 and 1280, light and dark.
- `*-testify-*`, `*-cite-*`: that pane open.
- `bill-testify-390-forced`: high-contrast mode.
- `bill-cite-386-chicago`: the width at which the lone full stop showed.

The new citation markup is written by the page build. For these shots, its rule (`shell.cite_url`) was applied to the three pages' built citations. The disk had no room for a full rebuild. The fixture build in preflight runs the real code.

## Measured in a browser

- **Panes:**
  - 54 openings on four kinds of page, at 360, 390, 1024 and 1280, light and dark.
  - The nub is on the pane's edge, at the button's middle, clear of the button, in the pane's colours.
  - On a desktop the pane is level with its button. On a phone it is under its button, as wide as the row.
  - No sideways scroll. No pane covers its own button. Escape closes the pane and returns focus to the button.
  - No button shows partly under a pane, at 360, 390 and 700.
- **Cite:** every width from 280 to 900px on three pages, 1,863 in all.
  - No line holds only a full stop or a comma.
  - No address's last part is split across lines.
  - No pane scrolls sideways.

## Not changed

- On a desktop, a pane opened from a lower button lies over the head beside it, as it always has. With the facts higher, Testify's pane now lies over COMMITTEE rather than over empty space.
- The minimum height is measured when a pane opens and when the window changes size. If the actions grew while a pane was open, it would not be re-measured. Nothing on the site does that today.
