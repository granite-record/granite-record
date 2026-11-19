# src/fetch/

Everything that asks another server, in one folder per whose server:
`gc_web/` (gc.nh.gov's web server: `refusal.check()`, the person starts it,
one at a time), `gc_db/` (the General Court's SQL host: ask first),
`youtube/` (a refusal stops the night's caption step; the evening job
it once stopped was retired on 10 October 2026) and `other/`. A fetcher
saves what it got; reading it is `parse/`'s job. The parsers that
`fetch_legislation --parse` and `fetch_committee_reports` carried are
`parse/legislation_text.py` and `parse/committee_report_text.py` since
19 November 2026, named in the fetchers as before; `parse/rollcalls_from_db`
still takes `VOTE_WORD` from `fetch_rollcalls_db`, where `live_gen` reads it.

Which folder a fetcher goes in is decided by whose server it asks, not by its
name or its subject: that is what decides what can go wrong. preflight holds
the line both ways (`src/README.md`).

Every fetcher moved into these folders in stages 1 to 4 (`src/README.md`).
The entry points that ask too stay outside them: `nightly.py` and
`netcheck.py` at the root, because a workflow, a scheduler or the person
names them there, and `livestreams.py` and `cloud.py` in `src/ops/`, which
the workflows run by path.
