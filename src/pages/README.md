# src/pages/

Reads the record (`data/`, the root JSON, `proceedings.csv`) and writes
`site/`: each bill's payload (`build_site_v2`), every page and the frame
around it (`shell.py`), the feeds, the CSV downloads and the search index.
The browser's files are here too, since stage 5: `bills.html`, the template
every record page is built from, and the `app.js`, `app.css` and `find.js` it
loads. `build_pages.py` copies all four into `site/` as they are, and the
builders read them here under the folder they run in, so a fixture lays out
its own copies the same way. Edit them here; `site/` holds copies.

Run by: `build_all.py`'s `plan()`, after the record is built. A new page is
`build_<page>.py` on `shell.py` plus one `Step()`.

Asks nobody. Does not belong here: deciding a fact (`parse/`). This folder is
the code; `site/` at the root is what it writes. (Not `src/site/`: the
`site/` line of `.gitignore` would hide a folder of that name at any depth.)

The files moved here in stages 2, 3 and 5 (`src/README.md`): the helpers the
page builders import in stage 2, the fourteen builders `build_all` runs as
steps in stage 3, and the browser's four files in stage 5.
