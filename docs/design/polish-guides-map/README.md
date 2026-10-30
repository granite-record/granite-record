# Polish: guides and the map (for 11 November)

The manager's batch of 29 October 2026, on branch `polish/guides-map`, cut
from dev after the guides bundle merged. Items (c), (d) and (e) reached dev
in that bundle for the 1 November release. Their screenshots are here as
asked, comparing dev before the bundle with dev after it. This branch itself
carries (a), (b) and (f).

Each shot is `<item>-<before|after>-<390|1280>-<light|dark>.png`. For the map
items (a) and (b), "before" is dev's `map.js` and `map.css` and "after" is this
branch's, both routed into the preview site's own pages and run on its real
`district_map.json`.

## (a) The map's Fit button is a zoom-to-fit icon

`a-fit-buttons-*` shows the three zoom buttons, and `a-fit-map-*` the map box.

- **The icon:** the button holds the exact SVG of the spec (four corner
  brackets, `stroke="currentColor"`, so forced colours draw it in
  ButtonText).
- **Its name:** its `title` is both its accessible name and its tooltip,
  "Zoom to fit", with no `aria-label` beside it (with both, a screen reader
  heard "Zoom to fit" twice). This matches the seating chart's button, and a
  new preflight check holds the map's to it.
- **Its size:** 44 by 44 pixels, the same box as − and + beside it, before and
  after.
- **The words behind it:** one key, `map.zoom_fit`, with the draft Spanish
  "Ajustar a la pantalla" (the seating chart's own), replaces the two it retires, `map.fit` ("Fit") and
  `map.fit_all` ("Fit the whole map").
- **The seating chart's Fit button** is in `build_pages.py`, which is the
  release session's, so it is theirs to change, from the same spec.

## (b) The Town Map tab zooms out far enough for every district

Dover is the town in every shot. The views:

- `b-town-open-*`: the map as the tab opens. It looks as before: the town fills
  the view.
- `b-town-senate-*`, `b-town-exec-*`, `b-town-cong-*`: the map just after
  choosing Senate, Executive Council or US House. Before, the town stays put
  and its district runs off the edges. After, the town's district of that
  kind is fitted to the view.
- `b-town-fit-*`: zoom to fit. Before, it shows only the town. After, it shows
  every district the town is in, on all four kinds, together.

What changed in `map.js`, on a town's own map (a framed map) only:

- **The frame:** the map's frame is the town's districts on every kind of
  district the map shows, not the town alone, so zooming out reaches all of
  them.
- **The opening view:** the town still fills the view when the tab opens.
- **The deepest zoom:** exactly what it was. It is worked out from the map
  box's own size, so a small town (New Castle, Martin's Location) zooms in
  as far as it did, and no further.
- **Choosing a kind of district:** this fits that kind's district to the view.
  On State House, the town's floterial district is fitted with it, and the
  floterials are inside the frame.
- **A resize** (a phone turned, a window narrowed) keeps the middle of the
  view where it was. A town's map now opens zoomed in, and without this a
  resize slid the view off the town. A map hidden with its tab and shown
  again stays where it was. The Officials map, which has no frame, is as on
  dev.
- **For the owner:** a town's map now opens zoomed in, so on a phone a swipe
  that starts on the map pans the map rather than scrolling the page. On dev
  the town's map could not pan at the size it opened, so the same swipe
  scrolled the page.

## (c) A law's citations stay whole on a phone (in dev's 1 November bundle)

`c-rsa-list-*` shows the discrimination guide's step with RSA 354-A:19.

- **Before:** at 390 the citation breaks after its hyphen, "RSA 354-" and
  "A:19" on two lines.
- **After:** each citation stays whole (`white-space: nowrap`), and the list
  wraps between citations, as a list.
- **Across every guide:** at 390, dev split 45 citations; after the fix, none.

## (d) A guide's steps are numbered from 1 in each part (in the bundle)

`d-steps-*` shows passport's Step by Step.

- **Before:** one list of 7.
- **After:** three parts under their own headings, numbered 2, 4 and 1.

## (e) In the Record: each law with its year, and one year menu (in the bundle)

`e-record-*` shows How to Vote's In the Record.

- **Before:** "Laws that changed it since 2020", each law marked "Became Law",
  and this term's laws with no year.
- **After:** every law with the year it passed, under one menu, "Show the laws
  passed in", whose choice applies to every chapter at once.

The "after" is the preview's own page, its In the Record redrawn by the
bundle's code from the laws the preview lists. On the real build the lists run
longer, because the 2020 cutoff is gone.

## (f) "New Hampshire Laws" on the Laws page

`f-laws-title-*` shows the Laws page's heading.

- **Where it is written:** the title is set in `build_rsa.py` (the heading,
  the share card and the citation), and the tab list's name in
  `constitution_tab.py`. Both now read "New Hampshire Laws".
- **The "after" shot:** the preview's page with that one string as the branch
  writes it.
- **Ownership:** neither file is the release session's. The manager has asked
  the release session to drop the same change from its plan.
