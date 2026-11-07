# A former member who sat in both chambers is listed under each (offered after dry run 2)

The branch is `fix/former-directory-both`, on top of dev d2a8e027 (the candidate of dry run 3).
It is offered on the laptop manager's word. The deep walk of dry run 183 found the directory
fault, and its review found the site search's; both came with the weekend release's joins.

## What was wrong

The weekend release joins the 34 people who sat in both chambers into one page each: the 30
the owner confirmed on 2 November, and four joined before.

**The directory.** The former-members directory, `/directory/former-legislators`, listed each
page once, under the page's own chamber.
- Eight people who sat in the Senate were listed under the House alone: Cilley, Leo Fraser,
  Edward (Ned) Gordon, Fenton Groen, Frederick King, Amanda Merrill, Andrew Peterson and Frank
  Sapareto. A reader looking down the Senate list for Ned Gordon (1999–2002) found Gilmour,
  Giuda, Gottesman.
- 26 who sat in the House were listed under the Senate alone.
- So the count line read "89 former senators and 1,662 former representatives". The record has
  97 and 1,688, and live says so, since live still has a page for each chamber.

**The site search.** It groups former members by the chamber their line starts with. A joined
person's line started with the page's seat ("SD3 · Senate 2009–2024 · House 1999–2002"). So
all 34 fell out of Former Senators and Former Representatives into a third group, Former
Members.

## What it does now

- **The directory lists a person who sat in both under each chamber.** Each chamber's list is
  everyone with years in that chamber (former.json's `service`).
  - Under the page's own chamber the row is as before: "Sen. Jeb Bradley R, SD3 · Senate
    2009–2024 · House 1999–2002".
  - Under the other chamber, the row has that chamber's title, and its years first: "Rep. Jeb
    Bradley House 1999–2002 · Senate 2009–2024". It gives no party and no seat. Both are the
    page's chamber's, and no source gives them for the other chamber. "Sen. Leo Fraser R, Merr
    37" would read as a Senate seat he never held. "Rep. Michael Downing R" would be wrong:
    he sat in the House as a Democrat.
  - Both rows link to the one page.
- **The count line counts everyone who sat in each chamber**, and says why the two add to more
  than the people listed: "97 former senators and 1,688 former representatives with a recorded
  roll call vote since 1999, by surname. The 34 who sat in both chambers are under each." A
  count of one is singular.
- **A joined person's search line starts with the page's chamber**, in a one-chamber row's
  shape, with the other chamber's years after: "Senate · SD3 · 2009–2024 · House 1999–2002".
  Over dry run 2's `former.json`, all 1,751 former members are now in Former Senators (89) or
  Former Representatives (1,662), and none in Former Members.
- Nothing else changes. The meta description still counts people, 1,751.

## The shots

The before shots are dry run 183's own page. The after shots are the same page with this
branch's list in place of its own, built by `former_page` over dry run 183's `former.json`.
Everything else on the page is the preview's.

| Shot | What it shows |
|---|---|
| `d1-count-before-1280-light.png`, `d1-count-after-1280-light.png` | The count line: 89 and 1,662, then 97 and 1,688 with the sentence about the 34. |
| `d2-senate-fg-before-1280-light.png`, `d2-senate-fg-after-1280-light.png` | The Senate list from Francoeur. Before, Fraser, Gordon and Groen are missing. After, they are there, each with the Senate's years first and no House seat, and Frederick King is further down. |
| `d1-count-*-390-dark.png`, `d2-senate-fg-*-390-dark.png` | The same on a phone, in dark mode. Neither scrolls sideways. |

## The checks

- `_movers_by_term`'s directory fixture holds:
  - a person who sat in both chambers is under each list, with each list's title, years and
    words;
  - the count line, singular and plural;
  - the joined search line starting with its chamber;
  - that the site search still groups by that word.

  With the old `build_indexes.py` in place, the check fails.
- Over the real `former.json` of dry runs 183 and 2, the built page counts 97 and 1,688, with
  34 people in both lists. The search lines group as above.
- `preflight --changed` passes on top of dev d2a8e027.
- An independent review found nothing blocking. Its should-fix findings were these:
  - the other chamber's party and seat;
  - Downing's party under the House;
  - the search grouping.

  All are fixed here.

## Not here

- Michael Downing's own page still calls him a Republican throughout. A party for each
  chamber's years is a larger change, for 24 November.
- Two people named David Pierce now sit side by side in the House list, as the owner's record
  says they are two people. The list already had two such pairs.
