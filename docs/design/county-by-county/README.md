# County by County: design

A tester asked for County Government to go county by county. The owner
approved it for 24 November 2026, through the manager session. This is the
design. The Spanish and the checks come after it is agreed.

## What it is

One new section on `/learn/county-government`, **County by County**. It sits
after *The Officers on the County Part of Your Ballot* and before *What the
County Pays For*. It is one heading in the page's index. Under a short
introduction are ten cards, two across on a desktop and one on a phone. They
use the page's existing body cards (`.l-who` and `.l-body`, as *Who governs
a county* does).

Each card has:

| Row | What it says | Its source |
|---|---|---|
| label | N state representatives | counted at build time from `records/districts/house.txt` |
| Commissioners | elected by the district's voters, or by **the voters of the whole county** (Carroll, Sullivan) | RSA 653:1, VI, the county's subparagraph |
| Commissioners' terms | staggered (two of three seats on each ballot, one for four years and one for two, rotating), or **two years, all three every election** (Hillsborough, Strafford); Grafton staggered "since the 2022 election" | RSA 653:1, VI |
| Sheriff and the other four officers | two years, or **four years** since the 2022 election (Rockingham) and the 2024 election (Coos) | RSA 653:1, V |
| County convention | the county's N state representatives, from M House districts | `house.txt`, which is RSA 662:5's table |
| Commissioner districts | folded: the towns in each district, in the statute's own words | RSA 662:4, the county's paragraph |
| foot | "The law:" with the three citations, each linked to its Laws page section | |
| foot | Who holds these offices now, linking to the Officials page's County Officials tab | |

Where a county differs from what most do, the words are bold, so the cards
can be told apart at a glance.

## Sources, and how they were read

There is no kit on the cloud machine, so the statute text was read from this
site's own Laws pages (`/laws/653`, `/laws/662`, `/laws/661`). Those pages
are built from the kit's statute table, `db/NH_RSA.psv`.

- RSA 653:1, VI gives every county's commissioner rules, and V the officer
  terms.
- RSA 662:4 gives the commissioner districts. The cards quote it word for
  word, including its own punctuation: Merrimack District 3 has no "and",
  and Strafford District 3 has "Barrington" without "the town of".
- The House counts from `house.txt` match RSA 662:5 county for county: 400
  seats in 203 districts, from Hillsborough 123/45 to Coos 9/7.

The build phase adds a check that holds `COUNTY_RULES` and
`COMMISSIONER_DISTRICTS` to `db/NH_RSA.psv` wherever the kit is present. It
skips on a cloud clone, as the other statute checks do.

## Not on the card yet: each county's website

None of the ten county websites is on hand. Nothing in git, `records/sources/`
or the printout index names one. The owner would save each county's home
page, or one list of all ten from an official source. Until then the cards
carry no website line rather than one from memory.

## Questions

1. **The link to the officers.** The Officials page's sections have ids
   (`#of-county-strafford`), but an address naming one does not open the
   County Officials tab (checked on the live site). So every card links to
   `officials#counties`, the top of the tab. Should the tab script open the
   tab that holds an addressed section, so each card can land on its own
   county? That is a small change to the tab script, which belongs to
   another session.
2. **A Common Question on vacancies**, from RSA 661:9, II: who fills a
   commissioner's seat (only the convention members from that district's
   towns and wards, where only the district votes; the whole convention
   where the whole county votes, or where fewer than 3 would be eligible).
   Add it?
3. **Cards or a table.** A ten-row comparison table is the alternative. On a
   phone it stacks into ten blocks with no room for the district lists. The
   recommendation is the cards.

## Shots

Preflight's fixture site built from this branch, served in the preview's
origin, at 2x. The fixture's district map is a stub, so the shots carry the
counts `house.txt` gives, which is what a real build counts.

- `c1-top-1280-light.png`: the heading, the introduction and the first cards,
  with the index beside them.
- `c3-all-1280-dark.png`: all ten cards.
- `c1-top-390-light.png`, `c2-strafford-open-390-light.png`,
  `c2-strafford-open-390-dark.png`: on a phone, with Strafford's districts
  open.

No horizontal overflow at 390 or 1280.
