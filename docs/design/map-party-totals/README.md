# Map party totals: the chamber shown, statewide, under the map's legend

The branch is `feat/map-party-totals`. It sits on `fix/presiding-line` 28a4fae1, which is on
`fix/members-elect-polish` 068ed8b0, which is on dev 92247871 (dry run 6).

Alice asked for it on 7 November 2026, through the laptop manager: "IF IT FITS: on the map, a
short list of the party totals for the chamber layer shown (Senate or House): Democrats,
Republicans, Independents, statewide."

## What it does

The district map is on two pages: the Officials page's My Town tab and each town page's Map
tab. On the State House and State Senate layers it now draws one line under the legend:

> STATEWIDE **House:** 212 Republicans · 169 Democrats · 1 Independent · 18 vacant
>
> STATEWIDE **Senate:** 16 Republicans · 8 Democrats

In Spanish, as drafts:

> EN TODO EL ESTADO **Cámara:** 212 republicanos · 169 demócratas · 1 independiente · 18 vacantes
>
> EN TODO EL ESTADO **Senado:** 16 republicanos · 8 demócratas

- **It follows the layer switch.** `legend()` redraws the line every time the layer changes, as
  it redraws the legend. On the Executive Council and US House layers the line is empty, and
  map.css does not draw an empty line (`.gmtot:empty`).
- **Where it sits.** Inside the legend's box (`.gmkey`), straight after the legend's swatches.
  - At 1280 that is the right-hand column, above the panel.
  - On a phone it is above the map, under the legend, where the legend already was.
  - The head is in the controls' small capitals, the same style as "LABELS".
  - The order is the legend's: Republican, Democratic, Independent, then Vacant.
- **What is counted.** It counts `who` in district_map.json: the sitting members the map
  colours the districts by. Nothing new is built or published for it.
  - The State House is its 164 base districts and its 39 floterials. `who_sits` puts each
    member in one of them, so a floterial's members are counted once, under the floterial, and
    never again under the districts below it. The seats add up to 400.
  - A vacant seat is a district's seats minus its sitting members, counted apart as "vacant".
  - Any party but R, D and I is said the way the panel's title already says one ("2 Ls").
- **What does not change.** The district colours, the legend, the panel, the list, the labels,
  the geometry and district_map.json's shape. `build_district_map.py` is not touched.
- **On the town pages too.** The line reads "Statewide", so on a town page it is not taken for
  the town's own count. A town's legend shows only the parties in its own districts.
- **A page can leave it out.** `mount(el, {totals:false})` does that. Neither page does.

### Why nothing for the Council and the US House

Those numbers would fit easily: Council 4 Republicans · 1 Democrat, US House 2 Democrats. They
are left out on purpose:

- The ask was for the chambers ("Senate or House").
- Those two bodies are not the General Court.
- Their five districts and two districts can each be counted on the map at a glance.

If Alice wants them, it is two more entries in `CHAMBER` and two words in the catalog.

## The counts seen, and the cross-check

On dry run 6 (https://7c76e0a0.graniterecord.pages.dev, built from dev 92247871), from its own
`/district_map.json`:

| Chamber | Seats | Republicans | Democrats | Independents | Vacant |
|---|---|---|---|---|---|
| House | 400 | 212 | 169 | 1 | 18 (in 18 districts) |
| Senate | 24 | 16 | 8 | 0 | 0 |

The Legislators tab's "Who holds the seats" on dry run 6's `/officials` draws the same:

- **Senate:** "24 of 24 seats filled", Republican 16, Democrat 8.
- **House:** "382 of 400 seats filled, 18 vacant", Republican 212, Democrat 169, Independent 1,
  Vacant 18. Its vacancy list names the same 18 districts the map counts short:
  - Belknap 2, 5, 6
  - Cheshire 1
  - Coos 6
  - Grafton 9
  - Hillsborough 1, 6, 24, 29, 39, 40, 41
  - Rockingham 5, 11, 22, 24, 25

They agree. The new data check reads the two files side by side on every night that has
them. Run on dry run 6's `district_map.json` and `home.json`, it says "ok".

The two counts come by two roads from the same roster:

- **The map** counts `site/legislators.json` through `build_district_map.who_sits`.
- **The tab** counts it through `build_site_v2.build_composition`, into `home.json`.

They could differ only if:

- the map placed a member in no district of its own (a county it has no code for), or
- a district held more members than seats.

The data check turns either case into a failure, and says which.

## The shots

All were taken with Playwright on dry run 6 as served. The "after" shots served this branch's
`map.js` and `map.css` in place through `page.route`. `map.js` is stripped of its comments
(strip_js.py), as the site publishes it.

- **Nothing else was replaced.** Dry run 6's own `district_map.json` was used, unchanged,
  because its shape did not change.
- **The base files match.** Dry run 6's `map.js` is the base's, stripped, byte for byte. Its
  `map.css` differs from the base's only in its line endings, so the "after" shots differ from
  the "before" shots by this branch alone.
- **The Spanish shots** also served dry run 6's own `/lang/es.js` with this branch's three new
  words added. Nothing else in it was changed.

| What | 1280 light | 1280 dark | 390 dark |
|---|---|---|---|
| State House, before | `before-house-1280-light.png` | `before-house-1280-dark.png` | `before-house-390-dark.png` |
| State House, after | `after-house-1280-light.png` | `after-house-1280-dark.png` | `after-house-390-dark.png` |
| State Senate, before | `before-senate-1280-light.png` | `before-senate-1280-dark.png` | `before-senate-390-dark.png` |
| State Senate, after | `after-senate-1280-light.png` | `after-senate-1280-dark.png` | `after-senate-390-dark.png` |
| Spanish, after (/es/officials) | | | `after-es-house-390-dark.png`, `after-es-senate-390-dark.png` |
| A town page (Lyme, Map tab), State House | `before-`/`after-town-lyme-house-1280-light.png` | | `before-`/`after-town-lyme-house-390-dark.png` |

Measured in the same runs:

- **No sideways scroll.** At 390 the page is 390px wide, in English and in Spanish. At 1280 it
  is 1280px wide.
- **On Council and US House** the line is empty and not drawn, at every width and in both
  languages.
- **Dark mode.** The line is drawn in the page's ink: rgb(230, 233, 232) in dark, rgb(28, 33,
  38) in light. Its head is the controls' ink-2.
- **What it costs on a phone (390, English).**
  - **State House:** the line wraps to two lines, so the map starts 50px lower than before.
  - **State Senate:** one line, so the map starts 29px lower.
  - **In Spanish** the Senate line wraps to two lines (42px).
- **At 1280** the map does not move. The panel beside it starts 50px lower on State House and
  29px lower on State Senate.

## The checks

Two checks are new in `preflight.py`.

### `_map_party_totals` (frontend; it runs in `--code`)

map.js runs in node, mounted as the existing legend check mounts it, on three maps:

1. **A roster of real seats.** The map is built from the tracked files.
   - The House roster: a Republican and a Democrat in Hillsborough 21, an Independent in
     Strafford 7, two Democrats in the floterial Hillsborough 40, and one in Merrimack 10.
   - The Senate roster: Senate 16, 9 and 21.
   - `totals()` must equal that roster counted in Python, by chamber and party, each member
     once, over the district files' seats.
   - The line must read "Statewide House: 1 Republican · 4 Democrats · 1 Independent · 394
     vacant" and "Statewide Senate: 1 Republican · 2 Democrats · 21 vacant".
2. **Every seat filled but one.** It must say "1 vacant", and nothing at all about vacancies
   where there are none.
3. **The fixture's built `district_map.json`.** Its numbers must be those the fixture's
   Officials page draws under "Who holds the seats".

For each map, the check holds:

- **The words.** The line is the catalog's words in English, and in Spanish with none of the
  English left.
- **Each count whole.** Each count is in its own unbreakable span.
- **It follows the switch.** The line mounted under the legend follows the switch through
  State House, State Senate, Council, US House, State House, State Senate. It is empty on
  Council and US House.
- **Placement.** mount() writes it right after the legend, and not at all with
  `{totals:false}`.
- **The CSS.** map.css hides the empty line and keeps each count whole.

A mutation was tried and caught: dropping the floterials from the House count, and giving the
Council a total.

### `_map_totals_published` (data; it runs on a night with `site/`)

The night's `site/district_map.json` is counted by map.js. That count is held against
`site/home.json`'s composition, which is what "Who holds the seats" draws. The seats, each
party's members and the vacant seats must all be equal.

- With no `site/` it skips, as it does in a cloud session.
- On dry run 6's two files it says "ok", with the two lines above.
- With one Democrat added to the composition it fails, naming both counts.

### The whole suite

`preflight.py --code` on this branch's tree reported **991 passed, 0 failed, 9 skipped**.

- The new frontend check is among the 991.
- The new data check is a data check, so `--code` leaves it out.
- The 9 skips are what this cloud session does not have on disk: no built `site/`, no
  `reports/TRIAGE.md`, no Windows PowerShell, no GRANIT zips.

## Files

- `src/pages/map.js`. Adds `totals()` and `totalsLine()`, both pure and both
  exported on GRMap. Adds the `.gmtot` line in the legend's box, redrawn by `legend()`, and the
  `totals` option.
- `src/pages/map.css`. Styles `.gmtot`, its head and its unbreakable counts, and
  does not draw it when it is empty.
- `src/pages/lang/es.json`. Three new drafts:
  - `map.statewide`: "En todo el estado"
  - `map.tot_base`: "<b>Cámara:</b> {list}"
  - `map.tot_senate`: "<b>Senado:</b> {list}"

  The counts reuse the map's existing words (`map.r_many`, `map.n_vacant`, and the rest).
- `preflight.py`. The two checks.
- `versions.json`. The three stamps, each one past the base: map.js, map.css and preflight.py
  (`python3 src/ops/inventory.py` prints them).
