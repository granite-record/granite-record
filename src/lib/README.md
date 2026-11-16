# src/lib/

Shared by every stage:

- `proceedings`: the one table's reader, and the term arithmetic about
  forty modules use;
- `freeze_term`: a finished term's frozen inputs, and also the command run
  at the term switch;
- `terms`: the term arithmetic by year (`term_of_year`), and which of the two
  term rules is which (the other, by date with Organization Day, is
  `proceedings.term_on`);
- `htmlesc`: the escapes that mirror components.js's `esc` byte for byte;
- `site_read`: a record read back out of the built site;
- `build_date`: the build's one clock;
- `child`: a child process without Windows' code-page crash;
- `keys`: the one place a credential is read (`secrets.json` at the
  repository root, wherever `keys.py` sits);
- `build_inputs`: what the last full build was built from, recorded by
  `build_all.py` in `logs/last-build.json` as a build ends well, and what
  has moved since -- read by the fast path (`src/pages/front_end.py`) and by
  `src/checks/site_manifest.py`;
- `build_cache`: answers a build step worked out on an earlier run, kept in
  `.build_cache/` under a sha256 of their inputs and their code, and carried
  to the night by the kit -- used by `parse/build_bill_versions.py` and
  `parse/officers.py` (which `pages/` reads twice a build);
- `build_io`: what each step of a build reads and writes, recorded while it
  runs -- started by `_paths.py` in every process of a step `build_all.py`
  names a folder for, and joined by `build_all.py` into
  `logs/build-io.json.gz` and the "io" of `site/build.json`;
- `people`: one entry a person, joining every number the General Court uses
  for them (an employee number, a PersonID in each chamber) under one
  person number, by the rule it states; the public people file and the
  register in `ops/person_numbers.py` both come from it, so the night and
  the run that issues numbers cannot join two people differently. Writes
  nothing and asks nobody;
- `spellings`: a member's name as the record misspells it, and the surname
  it means -- the "spellings" section of
  `corrections/member_corrections.json`, read here and never written;
- `state_settings`: the state's facts (its counties, time zone, legislature,
  and its offices and kinds of district, each with its article of the
  Constitution where it has one) read from `state_settings.json` beside it,
  so a fork for another state edits data rather than code; preflight holds
  every key and fails on a second literal county list;
- `entities`: the model of people, offices, terms, districts and elections --
  the shape of each kind of record, the rules a model holds to, and the
  views that give today's files back from it -- which `parse/build_entities.py`
  writes to `data/entities/` every night and nothing reads yet; what is the
  state's in it is `state_settings.json`'s;
- `gr_ids`: Granite Record's own ids, `gr-` and a serial, for a person the
  record names and the General Court gives no number, kept in their own field
  (`granite_id`) and never in `gc_employee_number`: the register's reader and
  the checks that hold the two apart, used by `ops/gr_register.py` and
  `parse/build_past_roster.py`.

A module comes here only when scripts in several folders import it and it
belongs to no single stage. A helper used by one folder lives in that
folder, and a later stage importing an earlier stage's module (`pages/`
importing `parse/`) does not make it shared. `_paths.py` is not here: it
stays at the root, where every script's bootstrap looks for it.

Five of the six moved here in stage 2 (`src/README.md`). `freeze_term` is
also the command run at the term switch, so it moved in stage 4, with the
lines that name it: `python3 src/lib/freeze_term.py --session`.
