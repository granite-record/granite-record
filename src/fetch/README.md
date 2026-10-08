# src/fetch/

Everything that asks another server, in one folder per whose server:
`gc_web/` (gc.nh.gov's web server: `refusal.check()`, the person starts it,
one at a time), `gc_db/` (the General Court's SQL host: ask first),
`youtube/` (a refusal stops the evening caption job) and `other/`. A fetcher
saves what it got; reading it is `parse/`'s job. `fetch_legislation --parse`
and `fetch_committee_reports` still carry parsers that `parse/` imports.

Which folder a fetcher goes in is decided by whose server it asks, not by its
name or its subject: that is what decides what can go wrong. preflight holds
the line both ways (`src/README.md`).

Every fetcher moved into these folders in stages 1 to 4 (`src/README.md`).
The entry points that ask too stay outside them: `nightly.py` and
`netcheck.py` at the root, because a workflow, a scheduler or the person
names them there, and `livestreams.py` and `cloud.py` in `src/ops/`, which
the workflows run by path.
