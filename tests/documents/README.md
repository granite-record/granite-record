# The text canary's fixtures

This folder is the proof, asked of every night that the calendars and
journals are handed to (or the switch is on), that GitHub's machine makes
the same text from a calendar or journal PDF as the laptop does. Until it
holds that proof the night asks the General Court for no document and makes
no text, and `cloud.py hand-over` refuses.

    python3 src/parse/extract_calendar_text.py --canary tests/documents

takes every PDF here, makes its text the way the night does, and compares it
with the `.txt` beside it, line for line (a line's end, Windows' or Linux's,
aside). It passes only when every pair is the same. With no pair here it says
`not proved` -- no fixtures is never a pass.

## What to put here (the person's job, on the laptop)

Eight files: four PDFs and the laptop's own text of each, one of each kind,
from 2025 or 2026:

| Document          | Where it is on the laptop                     |
|-------------------|-----------------------------------------------|
| a House Calendar  | `calendars\2025\` or `calendars\2026\`         |
| a House Journal   | `journals\2025\` or `journals\2026\`           |
| a Senate Calendar | `calendars_senate\2025\` or `\2026\`           |
| a Senate Journal  | `journals_senate\2025\` or `\2026\`            |

1. Choose four whose entry in `archive\extracted.json` says `"ok": true` and
   `"how": "pdftotext -layout"`, small ones (under about 1 MB) if there is a
   choice: every clone carries them.
2. Copy each PDF and its `.txt` here together, keeping their names, with
   Explorer or `copy` -- never by saving the text from an editor.
3. Run the canary above on the laptop. It should print
   `text canary: identical for 4 of 4, by pdftotext -layout; pdftotext version ...`.
   If it prints anything else, choose others.
4. Commit the eight files on `dev`.

A `.pdf` without its `.txt`, or a `.txt` without its `.pdf`, fails the canary.
This README is not a fixture.

## What it does not prove

That the night reads every document as the laptop does: only these four. The
night's own checks of each text are the guard for the rest
(`nightly.make_texts`): a calendar's text must carry its own number on its
masthead and a journal's its chamber's heading, and a journal's text goes in
only once the build's two journal readers pass with it. A text that fails is
not kept, its PDF stays in the bucket, and the night names the document for
a person every night, with `docs-accept` among the choices
(`watchers/README.md`).
