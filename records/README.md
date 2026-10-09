# records/

Official lists and documents, kept as they were published. Nothing here is
edited by hand or rewritten by a build; a correction goes in `corrections/`.

- `rollcalls/` -- the roll calls of every past session year since 1999,
  `RollCallSummary_<year>.txt` and `RollCallHistory_<year>.txt`, in the shape
  of the General Court's download. The General Court publishes only the
  current session's file, so a past year is here and nowhere else:
  `src/fetch/gc_db/fetch_rollcalls_db.py` read it out of the General Court's
  database, or `src/lib/freeze_term.py` kept it when the term ended. Read by
  `src/parse/build_data.py`, `src/parse/rollcall_parser.py` and
  `src/hearings/build_floor_index.py`.
- `districts/` -- the congressional, Executive Council, Senate and House
  districts and the towns and wards in each, which the town lookup stands on.
  `src/towns/parse_districts.py` reads them every night;
  `src/towns/parse_sos_districts.py` holds them against the Secretary of
  State's published table.
- `sources/` -- documents saved byte for byte: the Secretary of State's clerk
  and polling-place list, county roster and district table, and NHDOT's
  directory of municipal officials. The readers in `src/towns/` turn them
  into the files in `collected/`. NH GRANIT's shapefiles go in `sources/gis/`
  and are not tracked.
- `docket_abbrev.json` -- the General Court's own key to its docket's
  abbreviations, copied verbatim; read by `src/parse/referrals.py`.

The current session's files from the General Court -- `Docket.txt`,
`RollCallSummary.txt`, `GeneralCodes.txt` and the rest -- are at the root,
where the night installs all fourteen every day.
