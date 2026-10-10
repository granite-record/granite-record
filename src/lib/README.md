# src/lib/

Shared by every stage:

- `proceedings`: the one table's reader, and the term arithmetic about
  forty modules use;
- `freeze_term`: a finished term's frozen inputs, and also the command run
  at the term switch;
- `site_read`: a record read back out of the built site;
- `build_date`: the build's one clock;
- `child`: a child process without Windows' code-page crash;
- `keys`: the one place a credential is read (`secrets.json` at the
  repository root, wherever `keys.py` sits);
- `build_inputs`: what the last full build was built from, recorded by
  `build_all.py` in `logs/last-build.json` as a build ends well, and what
  has moved since -- read by the fast path (`src/pages/front_end.py`) and by
  `src/checks/site_manifest.py`.

A module comes here only when scripts in several folders import it and it
belongs to no single stage. A helper used by one folder lives in that
folder, and a later stage importing an earlier stage's module (`pages/`
importing `parse/`) does not make it shared. `_paths.py` is not here: it
stays at the root, where every script's bootstrap looks for it.

Five of the six moved here in stage 2 (`src/README.md`). `freeze_term` is
also the command run at the term switch, so it moved in stage 4, with the
lines that name it: `python3 src/lib/freeze_term.py --session`.
