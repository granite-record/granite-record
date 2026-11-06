# Polish from the cohesion audit (for 24 November)

The manager's block of 6 November 2026, on branch `polish/audit-24nov` from
dev 2e32416. It fixes the POLISH items of
`docs/design/cohesion-audit/REPORT.md` that were still present on that dev,
and leaves alone what the manager kept out of it (the record head and action
rail, guides and Learn, Live, the Resources tabs).

Each shot is `<item>-<before|after>-<390|1280>-<light|dark>.png`.

**How the shots were made.** A cloud session has no data to build the site
from, so "before" is the preview (dry-run.graniterecord.pages.dev) as it
stood on 6 November. "After" is the same preview with this branch's exact
text changes applied to `app.js`, `app.css` and the page as the browser
loaded them. The proof that the branch builds is preflight's: it builds the
whole site on its fixture and runs `app.js` in node.

## Fixed

| Item | Was | Now | Files |
|---|---|---|---|
| P-1 | The footer's "What do you think?" button sat flush on the line below it (a 0 px gap at every width) | An 8 px gap (`--sp-4`) | `app.css` |
| P-5 | A 1995 hearing read "HB 1-A - Committee Of Conference": `stationTitle` capitalised every word | "Committee of Conference", through the site's own `kindTitle`, which keeps a small word small | `app.js` |
| P-7 | The 404 page said it twice: a box "NO PAGE AT THIS ADDRESS" over the heading "Nothing is published here" | The heading alone | `build_pages.py` |
| P-8 | "No report is dated this meeting; the docket dates the committee's report May 14, 2026." | "The docket dates the committee's report May 14, 2026, not this meeting." Plainer, and like the old line it does not say the committee did not vote here: a Senate report's date is the sitting that took it up, and an older House row has no vote date | `app.js` |
| P-9 | The Calendar's week view announced each day as "Monday Nov 2 : open this day" (measured in the accessibility tree) | "Monday Nov 2: open this day", starting with the words on the button so a voice command still finds it; no visible change | `build_calendar.py` |
| P-12 | Documents tab: "House Calendar 12, 2026, committee report" read as a date, December 2026 | "Committee report, House Calendar 12 (2026)". The citation itself is the General Court's and is unchanged on the Reports tab | `build_site_v2.py` |
| P-13 | Seating chart: the "Find" label sat beside its box, while "Go to a seat" wrapped above its menu on a phone | Each label above its control, at every width, labels aligned | `build_pages.py`, `app.css` |
| P-15 | A member's vote dates and a statute's breadcrumb links were 16 px tall | A tap area of 24–27 px, from padding on the inline link, which still wraps as before. No line moves: page heights, a row's position and the heading's position measured the same before and after at 390 and 1280 | `app.css` |

Plus the version stamps (`versions.json`).

## Checks

- `preflight.py --code`: 0 failed (run under Python 3.14, the project's; the
  cloud box's own 3.13 lacks `sys.monitoring.events.BRANCH_LEFT`, which one
  check needs, and fails it whatever the branch).
- An adversarial review of the diff. What it found, and what was done:
  - **P-8 as first written claimed "No vote at this meeting".** That is not
    known for a Senate report or an older House row. Reworded so it claims
    nothing the record does not say.
  - **P-9's spoken name did not contain the button's visible words**
    (WCAG 2.5.3). It now starts with them.
  - **P-15 as first written made the RSA breadcrumb link an inline-block**, so
    a long Title name would drop whole to a second line on a phone. It is now
    padding on the inline link.
  - **P-1 would halve a 16 px default margin**, it said. Measured: the margin
    was 0 at every width, and is 8 px now. No change.
  - It checked and passed P-5, P-7, P-12, P-13 and the version stamps.

## Not done, and why

- **P-2, P-4** (the bill head's empty band, the Cite panel's lone full stop):
  the record head and Cite panel belong to another session.
- **P-3** (the committee line starting with "·"): by design. The audit of 25
  October (S9, `app.css` near "THE DOT GOES WITH THE ITEM AFTER IT") moved
  each dot to the head of the item after it, so that a line never ends on a
  dot. A line that starts with one is the price of that. The manager agreed.
- **P-6** ("Hover over a term"): Learn belongs to the guides session.
- **P-10** (`committee/s42` in lower case): it is the General Court's own code
  for Senate Education Finance, and "ss" is the deliberate prefix of a
  statutory or study committee. A new address would need a `_redirects` rule.
  The manager agreed to leave it.
- **P-11**: mocked, not built (below).
- **P-14** (the analytics error in the console): a check only. On
  graniterecord.org the Web Analytics beacon loads with no error; the CORS
  error is only on the pages.dev preview, whose address the beacon is not
  registered for. Nothing to fix.
- **P-15, the home page's session date link**: left alone. It sits in the
  home page's live slot, which live/session is changing, and it is a link
  inside a sentence, which the 24 px rule exempts.

## P-11, a mock for the owner (not built)

On a phone, the home page's Recent Session Days stacks two full-size video
players, one per chamber, about 460 px between them, before the Calendar and
Latest Activity. Two options, mocked in the browser on the preview, at 390,
light and dark:

- `p11-today-390-*.png`: as it is.
- `p11-option-a-one-player-390-*.png`: one player, the House's, and the
  other chamber's day a line with a Play link. Saves about 190 px. It needs a
  rule for which chamber gets the player; the mock takes the first listed.
- `p11-option-b-play-links-390-*.png`: no player, a line per day with a Play
  link. Saves about 420 px; the card is three lines.

It changes the home page's layout, so it needs the owner's choice.
