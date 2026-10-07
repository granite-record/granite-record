# src/pages/

Reads the record (`data/`, the root JSON, `proceedings.csv`) and writes
`site/`: each bill's payload (`build_site_v2`), every page and the frame
around it (`shell.py`), the feeds, the CSV downloads and the search index.
After the optional front-end stage, the browser's files (`app.js`,
`find.js`, `app.css`, `bills.html`) are here too.

Run by: `build_all.py`'s `plan()`, after the record is built. A new page is
`build_<page>.py` on `shell.py` plus one `Step()`.

Asks nobody. Does not belong here: deciding a fact (`parse/`). This folder is
the code; `site/` at the root is what it writes. (Not `src/site/`: the
`site/` line of `.gitignore` would hide a folder of that name at any depth.)

The files move here in stages 2 and 3 (`src/README.md`); until a file's
stage, it is still at the repository root.
