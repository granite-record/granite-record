# src/fetch/gc_db/

Scripts that connect to the SQL host the General Court publishes
credentials for at gc.nh.gov/downloads. This is not the web server that did
the blocking, so a refusal here has a different cause, but it is still
somebody else's server: ask first. `probe_db.py` is the connection they all
share; `probe_db.run_to_file` streams an answer too big for the JSON bridge.

Run by: the night's database fallback (`fetch_day_db`, when the export
comes back empty), the weekly (members, committee rosters), `build_all`'s
network steps, and a person.

Does not belong here: anything that reshapes what is already in `db/`. The
`*_from_db.py` scripts ask nobody and live in `parse/`.

The scripts move here in stages 1 to 4 (`src/README.md`); until a script's
stage, it is still at the repository root.
