# County by County

A tester asked for County Government to go county by county. The owner
approved it for 24 November 2026, through the manager session. The design
was agreed on 5 November: cards rather than a table, each card linking to
its own county on the Officials page, a Common Question on vacancies, and no
website line until a source for it is on hand. This is the build.

## What it is

One new section on `/learn/county-government` and `/es/learn/county-government`,
**County by County** (*Condado por condado*). It sits after *The Officers on
the County Part of Your Ballot* and before *What the County Pays For*. Under
a short introduction are ten cards, two across on a desktop and one on a
phone. They use the page's existing body cards (`.l-who` and `.l-body`).

| Row | What it says | Its source |
|---|---|---|
| label | N state representatives | counted at build time from `records/districts/house.txt` |
| Commissioners | elected by the district's voters, or by **the voters of the whole county** (Carroll, Sullivan) | RSA 653:1, VI, the county's subparagraph |
| Commissioners' terms | staggered (two of three seats on each ballot, one for four years and one for two, rotating), or **two years, all three every election** (Hillsborough, Strafford); Grafton staggered "since the 2022 election" | RSA 653:1, VI |
| Sheriff and the other four officers | two years, or **four years** since the 2022 election (Rockingham) and the 2024 election (Coos) | RSA 653:1, V |
| County convention | the county's N state representatives, from M House districts | `house.txt`, which is RSA 662:5's table |
| Commissioner districts | folded: the towns in each district, in the statute's own words | RSA 662:4, the county's paragraph |
| Website | only for a county in `civics.COUNTY_SITES` (empty for now) | the page the address is read from |
| foot | "The law:" with the citations, each linked to its Laws page section | |
| foot | Who holds these offices now, linking to `officials#of-county-<name>` | |

Where a county differs from what most do, the words are bold.

A new Common Question, *Who fills a commissioner's seat that falls vacant?*,
comes from RSA 661:9, II: who votes, the case of fewer than 3, the
whole-county case, and the 30-day limit before the primary ballots.

## In Spanish

The cards are drawn once in each language (`civics.county_cards(lang)`),
in the slot the shorthand table on Using This Site uses (`guides.topic_body`
leaves them as `<!-- counties -->`). The catalog therefore holds 22
`learn.counties.*` entries with `{n}` in them, not ten copies of each
sentence. RSA 662:4's words stay the law's English, marked `lang="en"`, under
*Los municipios de cada uno, en el inglés de la ley*. All of it is draft.

## The link to the Officials page

Each card links to `officials#of-county-<name>`. Today that address does
not open the County Officials tab (checked on the live site). The release
session is asked to make an addressed section open its tab, since the tab
script is theirs.

## Sources, and how they were read

There is no kit on the cloud machine, so the statute text was read from this
site's own Laws pages (`/laws/653`, `/laws/661`, `/laws/662`). Those pages
are built from the kit's statute table.

- RSA 662:4's districts are quoted word for word, including the statute's
  own punctuation.
- The House counts from `house.txt` match RSA 662:5 county for county: 400
  seats in 203 districts.
- The county websites: none is on hand. The state-sources session is
  collecting the ten through the laptop runbook. A source for each goes in
  `COUNTY_SITES` as (address, the page it was read from, the day).

## Checks

- `_county_cards_statute` (data) holds every card to `db/NH_RSA.psv`:
  each county's subparagraph of 653:1, VI, the four-year officers of
  653:1, V, and 662:4's words. It skips where the kit is absent. On a
  stand-in table made from the Laws pages' text, it passes as read and fails
  on each of three planted changes: a staggered Strafford, a town moved out
  of a district, and Coos's officers back to two years.
- `_county_cards_built` (frontend) checks, on the fixture site, in both
  languages:
  - ten cards, in order;
  - each linked to its own county;
  - no figure left unfilled;
  - the Spanish in Spanish, with the statute marked English;
  - a Website row only for a sourced county;
  - no per-county copies in the catalog;
  - the build's guard in place.
- The build stops if `districts.json` names a House district in no county
  of the ten, which would leave a card short with no other sign.

## Shots

Preflight's fixture site built from this branch, served in the preview's
origin, at 2x. The fixture's district map is a stub, so the shots carry the
counts `house.txt` gives, which is what a real build counts.

- `c1-top-1280-light.png`, `c1-top-390-light.png`: the heading, the
  introduction and the first cards.
- `c3-all-1280-dark.png`: all ten cards.
- `c2-strafford-open-390-light.png`, `c2-strafford-open-390-dark.png`:
  Strafford with its districts open.
- `c4-es-strafford-open-390-light.png`: the same card in Spanish.

No horizontal overflow at 390 or 1280 in either language.
