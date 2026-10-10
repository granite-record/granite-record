# src/pages/

Reads the record (`data/`, the root JSON, `proceedings.csv`) and writes
`site/`: each bill's payload (`build_site_v2`), every page and the frame
around it (`shell.py`), the feeds and the changes files the email sender reads
beside them (`follow_changes.py`), the CSV downloads and the search index.
The browser's files are here too, since stage 5: `bills.html`, the template
every record page is built from, and the `components.js`, `app.js`, `app.css`
and `find.js` it loads. `build_pages.py` copies all five into `site/` as they
are, and the builders read them here under the folder they run in, so a
fixture lays out its own copies the same way. Edit them here; `site/` holds
copies. The district map is a module of its own: `map.js` and `map.css`,
which `build_district_map.py` copies beside `/district_map.json`, the one
file the map draws, and which a page mounts with `GRMap.mount()`.

The components are in two files with the same helpers under the same names
(9 October 2026): `components.py`, which the builders draw a person, a
committee, a chip, a date and a time with, and `components.js`, which every
page loads in its head before any script of its own, for what the browser
draws. A helper is pure and thin: a plain value in, a string out. `preflight`
runs both on every case in `tests/components_cases.json` and fails where they
answer differently, where one has a helper the other has not, and where any
part of a helper is reached by no case.

Every chip but a person's is `chip(word, classes, size)`: a bill's status, a
meeting's kind, a vote's result, a party's letter, the sign-ins, the finder's
kind and a version of the text, in the person chip's frame (3px corners, a
1px edge, a 3px bar in the chip's ink) at 14px, or 16px in a head (`"m"`).
`app.css` draws it once, in its SHARED region; the classes beside `chip` are
the family that colours it and the hook a page places it by. Its words are in
Title Case, written so where they are made, and a record's own capitals go
through `title_words`, which keeps the record's own abbreviations in capitals
(`chips.json`'s `capitals`). `preflight` fails a chip written by hand and any rule
that gives one a shape of its own.

The words the pages say are in `words/`, one JSON file to a kind (9 October
2026): `chips.json` (the chip's words and the class that colours each, and
the Status filter's categories), `meeting_kinds.json` (the kinds of meeting and
their colours), `votes.json` (the vote words the person approved) and
`glossary.json` (the record's shorthand, for the term popovers). Each keeps
its reasons under `_about`. `components.py` reads them as `WORDBOOK`, and the
build writes the same into `site/components.js` between its `WORDBOOK:START`
and `WORDBOOK:END` lines (`build_pages.with_words`), so the copy here holds
none of them and nothing types a table of words twice. Change a word in its
file; `preflight` holds the browser's `WORDBOOK` to Python's.

Run by: `build_all.py`'s `plan()`, after the record is built. A new page is
`build_<page>.py` on `shell.py` plus one `Step()`.

`front_end.py` is the fast path, `python3 build_all.py --front-end`: a change
to `app.css`, `app.js` or `find.js` alone, put into the site the last full
build made in seconds, through `build_pages.front_end`, the function the
build itself calls. It refuses, naming the file, when anything else the
build reads has moved since that build (`src/lib/build_inputs.py` keeps the
record), and it refuses a change to `bills.html`, which every page is built
from. A builder that starts making something of one of those three files is
taught to `front_end.py` and named in preflight's `FAST_PATH_READERS`.

Asks nobody. Does not belong here: deciding a fact (`parse/`). This folder is
the code; `site/` at the root is what it writes. (Not `src/site/`: the
`site/` line of `.gitignore` would hide a folder of that name at any depth.)

The files moved here in stages 2, 3 and 5 (`src/README.md`): the helpers the
page builders import in stage 2, the fourteen builders `build_all` runs as
steps in stage 3, and the browser's four files in stage 5.
