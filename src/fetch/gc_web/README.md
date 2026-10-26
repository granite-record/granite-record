# src/fetch/gc_web/

Every script here sends requests to gc.nh.gov, whose firewall has blocked
this address twice; another block costs days and an email to a Clerk's
office. Nothing here runs without the person's say-so, and never two at
once: look at `archive/.lock` and `logs/gc_lane.log` first
(`watchers/README.md`). Every script calls `refusal.check()` straight after
parsing its arguments, and preflight fails if one does not or if a script
outside this folder does. Every script records a refusal it meets with
`refusal.note()` and stops with status 2, and preflight fails one that calls
`refusal.check()` and never `refusal.note()`. `bill_status/legacy/bs2016/`
(`fetch_archive_bills`, `resolve_members`) is the path IT asked be requested
lightly on session days.

Run by: the night (`snapshot_gencourt`, `fetch_lsrs`,
`fetch_calendar_archive --listing`, and `fetch_calendar_archive --night`
while the repository variable `NIGHT_DOCUMENTS` is a number; all but the
snapshot only if they can finish by 12:00 UTC), the weekly
(`fetch_committees`), `build_all`'s network steps (not on `--local`), the
lane, and a person. Once the night fetches the newest calendars and journals,
the drain here leaves it those it will still ask for, and
`fetch_committee_reports` leaves it this year's and last year's House
calendars (`refusal.night_documents`).

Does not belong here: a script that only writes a gc.nh.gov link into a page
(`pages/`), or one that reads what was saved (`parse/`). `netcheck.py` and
`refusal.py` stay at the root.

The scripts moved here in stages 1 to 4 (`src/README.md`): the by-hand
fetchers and probes in stage 1, `fetch_legislation` in stage 2, `build_all`'s
network steps in stage 3, and what the night and the weekly run by name in
stage 4.
