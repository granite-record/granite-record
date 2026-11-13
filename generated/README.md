# generated/

What this project computes from its own record ahead of time, and git keeps
because it takes a run a person starts to make. Each is rewritten whole by
the run named beside it, never edited by hand.

- `careers.json` -- one record per person across every term they served,
  joining the General Court's employee numbers into people
  (`src/parse/build_careers.py`).
- `person_numbers.json` -- the register of person numbers the data API
  publishes (/data/people.json): each person's number, one of the General
  Court's own by a fixed rule (src/lib/people.py), and the General Court
  numbers it was issued for. Unlike the rest of this folder it is never
  rewritten: entries are only added, by `python3 src/ops/person_numbers.py
  --issue`, which a person runs, and a number once issued is never given to
  anyone else. The nightly reads it and never writes it (preflight holds
  that, and that it only grows). First issued 30 October 2026.
- `past_roster.json` -- who sponsored a bill in each term from 1989 to 1998,
  by chamber: one row a person, term and chamber, with the General Court's
  employee number (`gc_employee_number`, unchanged), the name its list of
  members gives, and the seat each bill printed; coverage against 400 House
  and 24 Senate seats in the file's `coverage`. Not a roster: a member who
  sponsored nothing has no row. No party. The House's call of the roll
  (`data/unh/roster/`, read by `src/parse/past_roll.py`) is a second source:
  a row carries the volumes whose roll names the same person, a name is
  placed on a number only where one of the term's sponsors fits it, and the
  names it could not place are listed in the file, attached to no one. The
  1994, 1996 and 1998 volumes' rolls are not read yet. Rewritten whole by a
  person's run,
  `python3 src/parse/build_past_roster.py --apply`, after
  `python3 src/parse/text_sponsors.py --apply` (`src/parse/past_roster.py` places each printed
  surname on a person, and only where the bill's own sponsor rows settle it).
- `gr_ids.json` -- the register of Granite Record's own ids, `gr-` and a
  serial, made for a person the record names and the General Court gives no
  employee number. Kept apart from the General Court's numbers in every file
  that shows either: `gc_employee_number` holds only the General Court's,
  digits only, and `granite_id` only a `gr-` id (`src/lib/gr_ids.py`). Like
  `person_numbers.json` it is never rewritten: ids are only added, by
  `python3 src/ops/gr_register.py --issue`, which a person runs, and one is
  never renumbered, reissued or deleted. If the General Court's number for
  such a person is found later, `--found` records it; the number becomes
  their key and the `gr-` id stays as an alias. Empty when first committed
  (13 November 2026): every person the sponsor route names has a number.
- `moved_addresses.json` -- every address a former member's page has moved
  from, {address: member id}, so each answers with a 301 to the page they
  have now, for good: their seat put right from the bills of their last
  term, or two of their numbers made one page. Like `person_numbers.json`
  it only grows: `python3 src/ops/record_moves.py` merges in what a build
  moved and never drops or re-points an address, a person runs it and
  commits the file, and every build reads it (build_site_v2.keep_moved),
  saying what it moved that is not recorded yet. First recorded 5 November
  2026.
- `person_links.json` -- links between an employee number and its PersonID
  that no General Court view this site reads makes, each settled by a
  person with its evidence. Written by hand only; preflight holds that no
  code writes it. One link, Joyce Fulweiler, 30 October 2026.
- `places.json` -- one list of New Hampshire's places, reconciling the five
  that count them differently (`src/towns/build_places.py`).
- `district_geometry.json` -- NH GRANIT's 2022 district boundaries and town
  outlines, simplified on shared arcs for the district map
  (`src/towns/build_district_geometry.py`, run on the laptop, where the GIS
  zips are). The night publishes it inside `/district_map.json`.
- `topic_model.json` -- the settings `src/parse/topic_model.py` runs with,
  the ones that won its scored comparison of 16 September 2026; a new
  comparison writes new ones.
- `alignment_score.json` -- the timestamp methods scored against the
  hand-timed truth, which the About page states
  (`python3 src/hearings/probe_alignment.py --truth --score-out`).

What the nightly build writes is not here. It is rebuilt on every run and
not tracked: `site/`, `data/` and the JSON beside them at the root, which
`.gitignore` names.
