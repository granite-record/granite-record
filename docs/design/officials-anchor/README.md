# A section's address opens its tab (for 11 November)

The branch is `fix/officials-anchor`. An address naming something inside a tab's panel, such
as `/officials#of-county-strafford` (Strafford's heading on County Officials), now opens the tab
holding it and lands on it, the heading marked with the site's pale wash and set a little below
the top of the window, as a Learn section is when an address names it. Before, it opened the first
tab, My Town, at the top of the page, and what it named stayed hidden.

The script is `build_town_pages.TABS_JS`, which the Officials page, the 320 town pages and the
Resources hub share, so the same is true on each of them. An address naming a tab (`#executive`)
and one naming nothing (`#results`, the skip link) open as before. The Constitution tab's own
script has opened an article's panel this way since 17 October (`constitution_tab.TABS_JS`).

Two more things, from the review:

- **The reader keeps their place.** The page is brought to the heading again once it has loaded
  and when the web fonts arrive, which can move it, but not on a reload or Back, where the
  browser puts the reader back where they were, and not once the reader has scrolled, clicked or
  pressed a key. On a slow connection the first version pulled a reader who had read on back to
  the heading when the page finished loading.
- **A link to a tab brings its strip into view.** County Officials' "by county in Legislators"
  link opened Legislators and left the reader where they were, partway down a 406-member list in a
  different tab (as the live site does today). The strip of tabs now comes back into view, as the
  Resources hub's own script already sets it for a tab's address.

## How the shots were made

Each shot is `<item>-<page>-<before|after>-<390|1280>-<light|dark>.png`, taken in Chromium once
the page had loaded, its fonts had arrived, and a second more.

- **Before** is the live site, graniterecord.org, on 6 November 2026.
- **After** is this branch: preflight's fixture site, built by the branch and served on the
  machine, with only the site's own web fonts let through. Its County Officials are read from the
  same hand-kept file as the live site's, so the same names show.

## 1. Arriving at /officials#of-county-strafford, a desktop (`a1`, `a2`)

`a1`, before: My Town is open at the top of the page; County Officials is not chosen and Strafford
is out of sight. `a2`, after: County Officials is open and the page is at Strafford County, its
heading washed and 20 pixels below the top of the window, nothing over it.

## 2. The same address on a phone (`a3`, `a4`, `a5`)

`a3`, before: My Town, at the top. `a4`, after: Strafford County, washed, near the top of the
window with its officers below. `a5`: the same in dark mode, where the wash is the dark theme's.

Not shown, and checked in the same build at both widths: a link inside the page to another tab's
section (from Federal Delegation to `#of-county-coos`) opens County Officials and lands on Coos
County, the address left as the link wrote it; the "by county in Legislators" link brings the
strip back to the top of the window with Legislators chosen; a reload after scrolling on keeps
the reader's place; and with the map's script held back four seconds, a reader who scrolled on
before the page loaded is not pulled back.
