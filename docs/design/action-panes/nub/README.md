# Each pane joined to its button (the owner's word of 6 November 2026)

This is on branch `fix/action-panes` at 655438f.

## What changed

- **A nub.** A small triangle sits on the pane's edge, pointing at the button
  that opened it.
  - On a desktop it is on the pane's right edge, at the button's middle.
  - On a phone it is on the pane's top edge.
  - It is the pane's own fill and border, drawn as one shape with the pane.
  - Its tip stops 2px short of the button.
- **On a phone, the pane opens under its own button.** It used to open under
  the whole set of buttons. Now it opens directly under the button that was
  pressed, as wide as the row of buttons. A band of the page's background
  hides the tops of the next row's buttons in the gap.
- **The wording.** A bill already in the other chamber, unheard there or
  tabled there, now reads "They may open again if the Senate holds its own
  public hearing." (or "the House" for a Senate bill).
- **Both placements and the nub use one shared rule**, so they apply on
  every page with these buttons.

## Shots

Each shot comes in two versions:
- `-before.png`: the branch as of 093556b, which is what the owner saw this
  morning;
- `-after.png`: the branch now.

The shots are:
- HB 1123 of 2026, with Testify open and with Cite open, at 1280 and 390,
  light and dark;
- the House's session day of 21 May 2026, the page that isn't a bill, with
  Cite open;
- on a phone, Report a problem open, the last button in the set, on HB 1123
  and on 21 May.

The before shots of HB 1123 at 390 show the old way: the pane hung below the
whole set of buttons.

## Measured in a browser

These were measured on the real built site, on HB 1123 and on 21 May, at
360, 390, 1024 and 1280, in light and dark: 30 openings, all clean.

- **The nub:**
  - its centre is on the pane's edge, to within 1px;
  - it sits at the button's middle;
  - its tip is clear of the button;
  - its fill and border colours are the pane's.
- **Desktop:** the pane is level with its button.
- **Phone:** the pane opens right under its own button, as wide as the row
  of buttons. This holds for the right-hand column (Testify) as well as the
  left (Cite, Report).
- **General:**
  - no sideways scroll;
  - the pane never covers its own button;
  - Escape closes the pane and returns keyboard focus to the button.
- **Large default text (24px):** the nub stays clear of the button on both
  phone and desktop. (This said the page scrolled sideways at 1280 at that
  size. That was the test, not the site: see `../polish/README.md`.)

## Not changed

- **Next row on a phone.** A short pane on a phone leaves the bottom of a
  lower row's button showing below it, because the pane lies over the
  buttons.
- **High-contrast mode.** In Windows high-contrast mode the band's colour is
  dropped, so the next row's button tops show in the gap. The nub takes the
  pane's own system colours.
