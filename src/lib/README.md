# src/lib/

Shared by every stage:

- `proceedings`: the one table's reader, the term arithmetic about
  forty modules use, and seconds into a recording as a clock (`hms`);
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
- `shadow_keys`: what a cache would have done, with nothing taken from one --
  after each step the build design names as cacheable, the key a cache would
  give each finished term's part of it and the step whole, which
  `build_all.py` compares with the last real night's (kept by `nightly.py`
  as `archive/shadow-keys.json.gz`);
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
  Constitution where it has one, and its one table of parties: each party's
  letter, the site's words for it, the forms the files print it in and its
  colours, with `party_letters` to read a printed party by it) read from
  `state_settings.json` beside it, so a fork for another state edits data
  rather than code; preflight holds every key, fails on a second literal
  county list, and holds every copy of the party table in the code to it;
- `entities`: the model of people, offices, terms, districts and elections --
  the shape of each kind of record, the rules a model holds to, and the
  views that give today's files back from it -- which `parse/build_entities.py`
  writes to `data/entities/` every night and nothing reads yet; what is the
  state's in it is `state_settings.json`'s;
- `slugs`: the one rule that makes a name an address (`slug`) and a
  town's page key (`town_slug`), which the builders, the town readers and
  `entities` call -- a module of its own, since importing `entities` is
  reading the model;
- `bench_ledger`: the bench's ledger, `review/checked.jsonl`, read one way by
  every reader (`checks/review.py`, `hearings/probe_alignment.py`): whose a
  line is (the owner's `hand`, or a contributor's `link:<id>` merged from the
  hosted bench), the owner's line beating a contributor's whatever the order,
  and a withdrawn link's lines read by no one. Reads one file, writes nothing;
- `election_law`: the election law's days by the text of the section in force
  on the day -- the state primary (RSA 653:8), the general election (RSA
  653:7) and the primary's filing period (RSA 655:14) -- read off
  `db/NH_RSA.psv` where it is in the run's folder, and off its own copy where
  not; used by `pages/key_dates.py` and `parse/parse_sos_primary_results.py`,
  which dates a State Primary by it. Standard library only;
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
