# src/checks/suite/

The modules of preflight's suite of checks. `preflight.py`, at the root, is
what is run, and holds every check; these are what it imports:

- `pf_core.py` -- the registry (`check`, `CHECKS`) and how a check's answer
  is read; the seal on a child that must reach no network (`_Seal`); the
  suite's word for itself (`_suite_files`, `_in_suite`, `_suite_namespaces`)
  and the switches every module reads (`_SWITCHED`); the repository's files
  read once (`_source`) and its scripts parsed once (`_parsed`); what a run
  came out as (`_OUTCOMES`, `_THIS_RUN`); and the manifest
  (`preflight.py --manifest`).
- `pf_fixture.py` -- the fixture project and the site twenty builders make of
  it, made once a run or beside the checks (`_fixture_site_shared`,
  `_start_early_builds`).
- `pf_harness.py` -- a page's script run in node as a browser runs it
  (`_with_components`, `_node_app`, `_app_js`).
- `pf_runner.py` -- `main()`: the arguments, the choice of checks, the run,
  its record and its slowest line; and the lists of the checks the night
  runs after its build (`BUILT_CODE`, `NOT_ON_THE_NIGHT`, `RECORD_CHECKS`,
  `REMINDERS`).

Each uses only those above it in this list, and none imports `preflight`.
The checks are here too, by the module each tests (`pf_<area>.py`, the
rule of reports/refactor/stage0-checks.md, section 7), with `pf_shared.py`
holding what two areas share; `ORDER.json` keeps the order a run takes
them in, which was the one file's. `pf_entities.py` holds the checks of the
model of people, offices, terms, districts and elections
(`src/lib/entities.py`), which reads several areas' files and is no one
area's; its checks are not in `ORDER.json`, and run after those it lists.
`pf_bench.py` holds the checks of the bench -- the ledger of a person's
judgments and its readers, and the shared bench's database, Functions, page
and laptop tools (approved 17 November 2026) -- one feature across four
folders; its checks are not in `ORDER.json` either, and run after those it
lists.
They were cut out of `preflight.py` as they stood, with the comments above
each (the refactor's stage 1, step 4, 16 November 2026); the next step moves
the checks here, by area, as `pf_<area>.py`, keeping the order a run takes
them in.

A name is unique across the code folders, so a module here is `pf_<what>`:
`_in_suite` takes `preflight.py` and a `pf_*.py` of this folder for the
suite's files, and the guards that read every code file pass over them as
they pass over `preflight.py`.

Run by: `preflight.py`, which imports all four. Does not belong here: a check
of something other than the repository's code, such as `check_site.py` and
`check_live.py`, which are in `src/checks/`.
