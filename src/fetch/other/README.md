# src/fetch/other/

Fetchers for everyone else: the Secretary of State (`fetch_town_clerks`),
towns' own websites (`town_sites`), and UNH's scanned journals and the
Internet Archive (`unh_survey`, `unh_fetch`, `unh_ia`). All are run by hand,
each with its own pacing; `refusal.check()` does not apply.

A new source's fetcher starts here unless it asks the General Court or
YouTube; its reader goes in `parse/`, or in `towns/` if it is about a town,
a district or a county. graniterecord.org is not a source: `check_live` is
in `checks/`.

The scripts move here in stage 1 (`src/README.md`); until then they are
still at the repository root.
