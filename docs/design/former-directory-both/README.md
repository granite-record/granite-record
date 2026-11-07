# A former member who sat in both chambers is listed under each (for dry run 2)

The branch is `fix/former-directory-both`, on top of dev 969c27fa (the weekend release). It is
offered for dry run 2, on the laptop manager's word. The deep walk of dry run 183 found the
fault, and it is new with the release.

## What was wrong

The weekend release joins the 30 people the owner confirmed into one page each. The
former-members directory, `/directory/former-legislators`, lists each page once, under the
page's own chamber.

- Eight people who sat in the Senate are now listed under the House alone: Cilley, Leo Fraser,
  Edward (Ned) Gordon, Fenton Groen, Frederick King, Amanda Merrill, Andrew Peterson and Frank
  Sapareto. A reader looking down the Senate list for Ned Gordon (1999–2002) found Gilmour,
  Giuda, Gottesman.
- 26 who sat in the House are listed under the Senate alone.
- So the count line read "89 former senators and 1,662 former representatives". The record
  has 97 and 1,688, and live says so: live still has a page for each chamber.

## What it does now

- Each chamber's list is everyone with years in that chamber (former.json's `service`). A
  person who sat in both is under each.
- Under the other chamber, a person is named as that chamber named them: "Rep. Jeb Bradley" in
  the House list, "Sen. Jeb Bradley" in the Senate's. Both link to the one page. The row's
  words are the same in both lists: the party, the page's seat, then each chamber with its
  years.
- The count line counts everyone who sat in each chamber, and says why the two add to more
  than the people listed: "97 former senators and 1,688 former representatives with a recorded
  roll call vote since 1999, by surname. The 34 who sat in both chambers are under each."
- Nothing else on the page changes. The meta description still counts people, 1,751.

## The shots

These are dry run 183's own page, before, and after: the same page with this branch's list
(built by `former_page` over dry run 183's own `former.json`) in place of its own. Everything
else on the page is the preview's.

| Shot | What it shows |
|---|---|
| `d1-count-before-1280-light.png`, `d1-count-after-1280-light.png` | The count line: 89 and 1,662, then 97 and 1,688 with the sentence about the 34. |
| `d2-senate-fg-before-1280-light.png`, `d2-senate-fg-after-1280-light.png` | The Senate list from Francoeur: Fraser, Gordon and Groen are missing before and present after, with Frederick King further down. |
| `d1-count-*-390-dark.png`, `d2-senate-fg-*-390-dark.png` | The same on a phone, in dark mode. Neither scrolls sideways. |

## The checks

- `_movers_by_term`'s directory fixture holds that a person who sat in both chambers is under
  each list, named for each chamber. It also holds the count line. With the old
  `build_indexes.py` in place, the check fails.
- Over dry run 183's real `former.json`, the built page counts 97 and 1,688, with 34 people in
  both lists.

## Not here

- Michael Downing is the one joined person whose party differs between chambers (D in the
  House, R in the Senate). His rows read R in both lists, as his page does. A party for each
  chamber's years is a larger change, for 24 November.
