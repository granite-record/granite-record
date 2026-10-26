# The text canary's fixtures

This folder is the proof, asked of every night, that GitHub's machine makes
the same text from a calendar or journal PDF as the laptop does, byte for
byte. Until it holds that proof, the night fetches no documents.

## Why it exists

The parsers that read the calendars and journals were written against the
text `pdftotext -layout` makes on the laptop: the calendars are set in
columns, and a different extractor puts a time on a different line from its
bill. The night makes the text of each document it fetches on its own
machine, so before it asks the General Court for anything it runs:

    python3 src/parse/extract_calendar_text.py --canary tests/documents

That takes every PDF here, makes its text the way the night would, and
compares it with the `.txt` beside it. It passes only when every pair is
identical. With no pair here it says "not proved" and fails — no fixtures is
never a pass — and the night then asks for no document at all.

## What to put here (the person's job, on the laptop)

Eight files: four PDFs and the laptop's own text of each.

| One of each, from 2025–26 | Where it is on the laptop                |
|---------------------------|------------------------------------------|
| a House Calendar          | `calendars\2025\` or `calendars\2026\`    |
| a House Journal           | `journals\2025\` or `journals\2026\`      |
| a Senate Calendar         | `calendars_senate\2025\` or `\2026\`      |
| a Senate Journal          | `journals_senate\2025\` or `\2026\`       |

1. **Choose four whose text this project's extractor made.** Open
   `archive\extracted.json` and pick documents whose entry says `"ok": true`
   and `"how": "pdftotext -layout"`. A text made some other way (by
   `fetch_senate_calendars.py`, say) is not what the night will compare
   against.
2. **Prefer small ones**, under about 1 MB each if there is a choice: these
   files are committed to git and every clone carries them.
3. **Copy each PDF and its `.txt` into this folder, together, keeping their
   names**, so that `HC012.pdf` sits beside `HC012.txt`. Copy the files with
   Explorer or `copy`; do not open the `.txt` and save it from an editor,
   which can change its line endings and so every byte the canary compares.
   Git keeps them as they are: `.gitattributes` marks `tests/documents/*.txt`
   as bytes (`-text`), so neither the commit nor the night's checkout
   converts their line endings, and preflight holds that.
   If two would share a name, rename the PDF and its text the same way.
4. **Run the canary on the laptop**, from the repository's root:

       python3 src/parse/extract_calendar_text.py --canary tests/documents

   It should print `text canary: identical for 4 of 4, by pdftotext -layout`,
   then the laptop's pdftotext version (`; pdftotext version ...`), which
   should be the 26.09.0 the night pins. If it prints anything else on the
   laptop, the text on disk was not made the way the extractor makes it now;
   choose others.
5. Commit the eight files on `dev`.

Nothing else belongs here. Any `.pdf` without its `.txt`, or `.txt` without
its `.pdf`, makes the canary fail. This README is not a fixture; it is
ignored.

## What it does not prove

That the night's machine reads every document the way the laptop does. It
proves that it reads these four the same, byte for byte, which is the most a
check that asks the General Court for nothing can prove. A document set
differently from all four could still come out differently. The night's
own checks of each text it makes are the guard for that
(`nightly.make_texts`): a calendar's text must carry its own number on its
masthead and a journal's its chamber's heading, and when a journal's text
goes in, the build's two journal readers are run on it with `--check` first.
A text that fails is not kept, the night's verdict lists it
(`documents_untexted`) with its cause, and the night's warning says what a
person does for that cause. Its PDF is kept in the bucket for every cause
but one: a PDF whose text was not the document's own is neither kept nor
held, and the night does not ask for it again (`nightly.tried_out`); a person
fetches it on the laptop with
`src/fetch/gc_web/fetch_calendar_archive.py --take` to open it.
A PDF whose text a journal reader refused comes down apart (`cloud.py
docs-down`, into `archive/documents-held/`) for a person to look at; the
others come down to their own folders, where the laptop's extractor can make
their text. Any text of such a document made later is read again by the
night before its build reads it.

On GitHub's machine the canary, like the night, runs only the pdftotext the
workflow pinned, and its sentence ends with that program's own version
(`; pdftotext version 26.09.0`), so a passing canary says which it proved.
On the laptop it runs the one on the PATH, and says which.
