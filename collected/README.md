# collected/

What was gathered from outside sources and git keeps, in this project's own
shape. A person refreshes each file by running the script named beside it,
and the diff is the review.

- `videos/` -- the House and Senate YouTube channels' indexes,
  `videos_<chamber>_<from>_to_<to>.csv`, written by
  `src/fetch/youtube/fetch_channel_index.py`, and `channel_index_full.json`,
  the walk of both channels. The night's new livestreams are not here: they
  are `videos_*_livestreams.csv` at the root, written by
  `src/ops/livestreams.py` and carried from one night to the next in the
  kit, never committed. Every reader takes both through
  `proceedings.video_indexes()`.
- `constitution.json` -- New Hampshire's Constitution, article by article,
  with nh.gov's notes on when each was adopted and amended, read from the
  pages saved in `records/sources/constitution/`
  (`src/parse/parse_constitution.py`). The Laws page's Constitution tab is
  drawn from it, and a CACR's page links the articles it would change.
- `town_clerks.json` -- each town's clerk and polling place, from the
  Secretary of State's list (`src/towns/parse_clerks_csv.py`); each row's
  `read_on` is the day of the export it was read from.
- `town_officials.json` -- NHDOT's directory of municipal officials
  (`src/towns/parse_officials.py`); each municipality's `as_of` is the
  directory's own date.

How old each of the town files is, and when each is due to be read again, is
`src/towns/town_sources.py`'s to say: `python3 src/towns/town_sources.py`.
- `town_officials_web.json` and `town_boards.json` -- what the towns' own
  websites say of their officials and boards (`src/towns/parse_town_sites.py`
  and `src/towns/town_boards.py`, from the pages
  `src/fetch/other/town_sites.py` saved under `town_sites/`, which is not
  tracked).
- `county_officials.json` -- the elected county officers, from the Secretary
  of State's county roster (`src/towns/parse_county_roster.py`).
- `sos_districts.json` -- the Secretary of State's district table, read off
  its PDF (`src/towns/parse_sos_districts.py`).
- `granit_layers.json` -- what each of NH GRANIT's district layers is, where
  it came from, and whether it agrees with the House districts
  (`src/towns/parse_granit.py`).
- `election_<year>.json` -- a general election's State Representative and
  State Senate results, as the Secretary of State posted them, by the race
  keys of `site/districts.json`; `src/parse/build_members_elect.py` reads the
  newest, and its docstring gives the shape. Written by
  `src/parse/parse_sos_results.py --year <year> --url <results page>` from
  the spreadsheets saved in `records/sources/`, the page they were saved from
  becoming the address `/members_elect.json` names, and `--check` says
  whether the two still agree.
  `election_2024.json` is the first, and the matching rule's test set
  (`src/parse/score_members_elect.py`).

The documents the town files were read from are in `records/sources/`.
