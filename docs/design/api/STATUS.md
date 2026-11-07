# Public data API: status

Written by the API session, 7 November 2026, for the manager on the laptop.
The latest commit on `design/api` carries the same status in its message.

## Done

- Branches 1 to 6 are in dev (checked 7 November: 03e05b81 and 13a4656b are
  ancestors of dev dd3f7ef9). The /api page is unlinked and noindexed, as
  planned until the December announcement.
- The 11 November train carries `fix/api-rights-youtube`:
  - proceedings.csv has no YouTube columns.
  - One approved rights line covers every download, with CC0 covering the
    spreadsheets too (the owner's word, 5 November).
- Proof for each branch: a full build twice, under two seeds, identical, and
  compared file by file with dev. The ready notes list every changed file.

## Parked, waiting on the owner or another session

- **Q18, YouTube watch links and titles.** Held by the owner. No API file
  carries them, and the build stops if a YouTube column comes back.
- **Branch 7, a stable key in the nightly change log.** Waits on the
  sessions that own following and the feeds.
- **Election results in the bulk files.** `docs/design/api/ELECTIONS.md`.
  - Questions QE1 to QE6 are for the owner, each with a default.
  - It is agreed with the election results design session: one shared
    "final" rule, a race enters only when all its seats are final, and a held
    winner keeps their race out.
  - Nothing is built until the owner answers.
- **CORS for schema.json and people.json.** Passed to the release session's
  `_headers` on 5 November. The /api page claims cross-origin access only for
  the manifest and the spreadsheets, which is true today.

## Worth knowing

- The proof builds reuse one build folder, so a dev build there still holds
  api.html and schema.json left by earlier branch builds. A comparison then
  shows them as "changed" rather than "added". Dev's code writes neither
  file.
- preflight's fixture writes no database and no people files. The check
  "the data API's schema.json describes every column it publishes" builds a
  small database itself, so those paths are tested.

## Needs an answer

Nothing is needed now. Write to `design/api` (or tell Alice) to start
QE1 to QE6, branch 7, or anything else.
