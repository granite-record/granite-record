# Accessibility sweep

A read-only accessibility check of a deployed copy of the site, first run on
29 October 2026 against the dry-run preview before release 1. It asks nothing
but the site it is pointed at (and npm, once, for axe-core). It changes
nothing and is not part of the build or of preflight. Run it before a
front-end release and compare against the results kept here.

## Running it

```
cd docs/design/a11y-sweep
npm install                      # axe-core 4.10.2, pinned in package-lock.json
node sweep.js                    # every page state, every view -> results/sweep.json, shots/run/
node measure.js                  # the repo's own measure() on the same views -> results/measure.json
node interactive.js              # keyboard and live-region checks, printed
node incomplete.js               # what axe could not decide on contrast -> results/incomplete.json
```

`A11Y_BASE=https://… node sweep.js` points it at another deployment; the
default is `https://dry-run.graniterecord.pages.dev`. `node sweep.js home,bill`
runs only the named pages (the names are in `PAGES` at the top of `sweep.js`).
The whole of `sweep.js` takes about twenty minutes, and `measure.js` about
forty.

## What each one checks

- `sweep.js`: 22 page states, each at 390 and 1280 px in light, dark, forced
  colours and 24px text (the browser's own text size, set through DevTools).
  It runs axe-core's WCAG 2.0 to 2.2 A and AA rules in light and dark, and
  checks sideways scroll, elements past the edge, text cut off in its box, the
  heading levels and the live regions on the page. At 1280, in light and in
  forced colours, it tabs through up to 120 stops, recording whether each has
  a visible outline, whether it is covered, and whether focus is trapped.
- `measure.js`: the `measure()` function of `src/checks/sweep_browser.js`, read
  from that file and run unchanged in the page. It checks contrast against the
  first solid background behind the text, overflow, overlap and cut-off text.
  The repo's own `rendered_sweep.py` serves a local build only, so this runs
  the same measuring on a deployed one.
- `interactive.js`: the Sections menu on a phone; the town tabs; the seating
  chart; the district map; Follow and Testify; whether the search boxes'
  live regions announce; and the search box's focus in forced colours.
- `probes/`: the one-off checks behind each finding of 29 October. Each one
  prints what it found.
  - `wide3.js`, `wide4.js`: what widens the Laws chapter page.
  - `inputs.js`: the search box's focus contrast.
  - `follow.js`: the seating chart, the map, forced-colours focus, and the search page.
  - `targets.js`: crowded tap targets under 24px.
  - `live2.js`: the home search status and copy announcements.
  - `more.js`, `party.js`: the menu, the bill tabs and the vote buttons.
  - `rings.js`: every focus style in use.
  - `axetest.js`: proves axe runs on the site, by planting two faults it must find.

Before trusting a clean axe result, run `probes/axetest.js`: it must report
`color-contrast:1` and `image-alt:1`.

## The results of 29 October 2026

`results/sweep-2026-10-29.json` and `results/measure-2026-10-29.json` are the
baseline. `shots/` holds the screenshots behind the findings. The report sent
to the manager session ranked them:

1. `/laws/659` scrolls sideways on phones, 258px too wide at 390. The cause is
   RSA 659:27-a's form, whose 70-underscore blanks never wrap
   (`laws659-390*.png`). WCAG 1.4.10.
2. Search boxes show no focus in forced colours, and in light and dark only a
   1px border change (`forced-hq-*.png`, `hq-*.png`). WCAG 2.4.7.
3. `/search` never announces its results (`search-typed.png`). WCAG 4.1.3.
4. Crowded tap targets under 24px: the Laws index links, and the bill and
   committee links on a legislator page. WCAG 2.5.8.
5. Tabbing out of the seating chart drops focus to the page. WCAG 2.4.3.
6. The vote tally's "this side prevailed" tick is in a tooltip only.
   WCAG 1.1.1 and 1.3.1.
7. Some headings are drawn smaller than the text they head. Cosmetic.

Clean on the same run: 0 axe violations in the 88 light and dark views, 0
contrast failures in all 176 (the lowest was 5.4:1), and no overlapping text.
Every control but the search boxes has a visible 2px outline, there are no
keyboard traps, and the map, tabs, menu, Follow and Testify all work by
keyboard.

None of this replaces a real screen reader (NVDA or VoiceOver). The run did
not cover the Spanish pages, 768 px, or Testify in its open state.
