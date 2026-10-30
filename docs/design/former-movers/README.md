# Former members who sat in both chambers (30 October 2026)

Branch fix/former-movers (f3534fa, off feat/api-people 898354e). The screenshots
compare that branch's build with the build of feat/api-people.

## What changed

A member who moves between the House and the Senate is given a new number in
each. `member_links.py` joins those numbers only for a member who sits today.
So once a mover left, their record stayed in two halves: one page per chamber.

The person register (`generated/person_numbers.json`, from `people.py` on
feat/api-people) is the join the public data API publishes. It joins 4 such
people. The site now takes the same join:

| Person | House page (now a 301) | Kept page, with both chambers |
|---|---|---|
| Shannon Chandley | 568, /legislator/shannon-chandley-hills-22 | 9404, /legislator/shannon-chandley-sd-11 |
| Erin Hennessey | 830, /legislator/erin-hennessey-graf-1 | 9836, /legislator/erin-hennessey-sd-1 |
| Martha Hennessey | 831, /legislator/martha-hennessey-graf-12 | 8738, /legislator/martha-hennessey-sd-5 |
| Harold French | 875, /legislator/harold-french-merr-2 | 8748, /legislator/harold-french-sd-7 |

The kept page is the later chamber's, as a sitting mover's is. It carries every
chamber's votes and terms. Chandley's page goes from 579 votes and 2 terms to
1,838 votes and 5 terms, and reads "On record 2009 to 2024". In the directory
she becomes one line, "Sen. Shannon Chandley, D, SD11, 2009–2024", where she
used to be two.

The redirects come first in `_redirects`, ahead of the tab rules, because
Cloudflare serves the first rule that matches. Each earlier page gets three:
its address, its `.html` spelling, and its tabs, so `/…/votes` goes to the
same tab of the kept page.

## Screenshots

- `senate-page-*-before`, `house-page-*-before`: her two pages before the join.
- `one-page-*-after`: the one page. Its "On record" line names both chambers.
- `*-votes-*`: the Votes tab, which opens on the latest term as before.

## The build, compared file by file

| What | Count |
|---|---|
| Files removed (the 4 earlier pages and their member files) | 8 |
| `_redirects`: per earlier address, the page, its `.html` and its tabs | 12 rules |
| Kept member pages and files that gain the other chamber | 4 + 4 |
| Bill and session pages | ~160 |
| Directory, find.json, sitemap, former.json, idx | yes |

On the bill and session pages, the link to an earlier page now points at the
kept one. Two other changes on House session days:

- **A seat tag drops on House-era speaker lines.** Where such a member spoke on
  a House day, the line now reads "Rep. Shannon Chandley" without "(D - Hills
  22)". Sitting movers are already drawn this way: Rep. Cindy Rosenwald on the
  same 2010 page has no seat tag either. It's existing behaviour, now applied
  to these four too. Showing the seat held that day is a possible follow-up,
  for movers of both kinds.
- **A leave list resolves.** On 2016-01-07, Martha Hennessey was an unresolved
  name in the leave list, so the party counts came to 64 of 65. Now she
  resolves, and Democrat goes from 27 to 28.

## Candidates no rule joins

`CANDIDATES.md` lists 31 same-name pairs across the chambers that no join
reaches. Each comes with evidence and a draft entry for the owner to confirm.
Nothing joins on a name alone, and nothing here writes `corrections/`.
