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
  repository root, wherever `keys.py` sits).

A module comes here only when scripts in several folders import it and it
belongs to no single stage. A helper used by one folder lives in that
folder, and a later stage importing an earlier stage's module (`pages/`
importing `parse/`) does not make it shared. `_paths.py` is not here: it
stays at the root, where every script's bootstrap looks for it.

The modules move here in stages 2 and 4 (`src/README.md`); until a module's
stage, it is still at the repository root.
