# src/ops/

The tools that keep the site running rather than build it: what the
workflows, the morning triage and a person run by its path.

- `cloud.py` -- the private R2 bucket: the nightly's kit and state going down
  and up, the built site handed between jobs, the laptop's backup and its
  pull. Both workflows run it as `python src/ops/cloud.py ...`.
- `livestreams.py` -- the night's new livestreams, indexed, captioned and
  read into the start times (`--since-state` in the nightly workflow,
  `--markers` in the build, `--catch-up` by hand on the laptop). It is the
  one script outside `src/fetch/youtube/` that asks YouTube, and preflight
  holds it to that. Since 17 October 2026 `--to-inbox` is the laptop's
  evening job under Task Scheduler: it asks YouTube for what the night's
  state lists as waiting and puts each caption file in the bucket's captions
  inbox, which the night takes with `--since-state --inbox` (cloud.py
  `inbox-down` before it, `inbox-clear` after the state goes back).
- `compile_reports.py` -- the reader reports from the report box's database,
  screened for the morning triage; the person's production pull.
- `inventory.py` and `handoff.py` -- a session's first and third commands:
  every file and its version, and `STATE.md` with the counts as measured.

Run each from the repository root, `python3 src/ops/inventory.py`; each finds
the rest of the code by bare name through `_paths.py`. They moved here from
the root in the root tidy (8 October 2026), and the workflows, the morning
triage's commands and the documents name the new paths.

Does not belong here: a step of the build (`src/parse/`, `src/pages/` and the
rest, in `build_all.py`'s `plan()`), or a fetch from the General Court
(`src/fetch/gc_web/`). `build_all.py`, `nightly.py`, `preflight.py`,
`refusal.py` and `netcheck.py` stay at the root, where a person or a workflow
names them. The laptop's evening job, `laptop_evening.py`, which Task
Scheduler ran there, went to `obsolete/` on 10 October 2026, when the night
took the captions over; YouTube then refused the night, and the captions
inbox (17 October 2026) gave the laptop back an evening job that writes no
state: `python3 src/ops/livestreams.py --to-inbox`.
