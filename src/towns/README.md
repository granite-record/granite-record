# src/towns/

New Hampshire's towns, wards, districts and counties, and the people who
hold their offices: the reference files the town pages and the "who
represents me" lookup stand on. The person split these out of `parse/` on
6 October 2026, so that `parse/` holds the legislature's record and this
folder the places it is elected from.

| What | Files |
|---|---|
| The places themselves | `build_places` (`generated/places.json`, one list reconciling the five on this disk) |
| Districts | `parse_districts` (`site/districts.json`), `parse_sos_districts` (the Secretary of State's own table, held against ours), `parse_granit` (NH GRANIT's geometry) |
| Clerks and polling places | `parse_clerks_csv` (`collected/town_clerks.json`), and `parse_clerks`, the PDF reader it supersedes |
| Officials | `parse_officials` (NHDOT's directory, `collected/town_officials.json`), `parse_town_sites` and `town_boards` (the towns' own websites), `parse_county_roster` (`collected/county_officials.json`) |

Nothing here asks the network. What these read was put on disk under
`records/sources/` and `records/districts/`, or saved under `town_sites/` by `town_sites`,
which is in `fetch/other/` with `fetch_town_clerks`.

Run by: `build_all.py`'s `plan()` for `parse_districts`, every night. The
rest are run by a person when a source changes, and each writes a committed
file, so the diff is the review; all of them but `parse_districts` take
`--report`, which says what it found and writes nothing.

Does not belong here: a request (`fetch/other/`), a legislator's record or a
bill's (`parse/`), the town pages themselves (`pages/`).

Six of the ten moved here in stage 1 and three in stage 2 (`src/README.md`):
`parse_officials`, `parse_town_sites` and `town_boards`, which the night
imports through `build_town_pages` and runs by no name. The tenth,
`parse_districts`, which the night runs as a step, moved here in stage 3.
