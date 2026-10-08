# src/ops/

The tools that keep the site running rather than build it: what the
workflows, the morning triage and a person run by its path.

- `cloud.py` -- the private R2 bucket: the nightly's kit and state going down
  and up, the built site handed between jobs, the laptop's backup and its
  pull. Both workflows run it as `python src/ops/cloud.py ...`.
- `livestreams.py` -- the night's new livestreams, indexed and captioned
  (`--since-state` in the nightly workflow, `--catch-up` in the laptop's
  evening job). It is the one script outside `src/fetch/youtube/` that asks
  YouTube, and preflight holds it to that.
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
`refusal.py`, `netcheck.py` and `laptop_evening.py` stay at the root, where a
person, a workflow or Task Scheduler names them.
