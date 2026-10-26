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
once the calendars and journals are handed to it and the repository
variable `NIGHT_DOCUMENTS` is a number), the weekly (`fetch_committees`),
`build_all`'s network steps (not on `--local`), the lane, and a person.

From the handover (`python3 src/ops/cloud.py hand-over`; `watchers/README.md`)
the night is the one machine that asks for the calendars and journals of the
handover's year and every year after it, and nothing here does: the drain
leaves those years out, `fetch_senate_calendars` stands down for them (exit
4), `fetch_calendar_archive --night` runs on GitHub's machine only, and
`fetch_committee_reports` reads the House calendars of a year ever handed
over from the disk, a hand-back included, and asks for none
(`refusal.night_years`, `refusal.handed_years`).

Does not belong here: a script that only writes a gc.nh.gov link into a page
(`pages/`), or one that reads what was saved (`parse/`). `netcheck.py` and
`refusal.py` stay at the root.

The scripts moved here in stages 1 to 4 (`src/README.md`): the by-hand
fetchers and probes in stage 1, `fetch_legislation` in stage 2, `build_all`'s
network steps in stage 3, and what the night and the weekly run by name in
stage 4.
