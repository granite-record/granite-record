# /api's counts say what they count (for 11 November)

The branch is `fix/api-units`, from dev `dd3f7ef9`. The deep walk of dry run 181's preview found
this on 6 November 2026. `/api` is new in the 11 November update, and live answers it with a 404,
so a reader would meet this new.

## What was wrong

`/api`'s downloads table is the data page's table. On the data page every count is of rows, the
column's head says Rows, and the word " rows" beside each count is drawn only on a phone, where
the heads are not (`.dpu`, app.css). `/api`'s counts are of five things: files, tables, people,
bills and rows. They had the same hidden unit under the same Rows head. So on a desktop the head
said Rows above a bare "43" for the files under `/data/` (the manifest's 42 and the manifest
itself) and a bare "14" for the database's tables (`u1-before.png`). A screen reader heard
"Rows, 43" too, since a hidden unit is hidden from it as well.

## What it does now

- **Each count says its unit at every width,** and the head says Count: "43 files", "14 tables",
  "2,187 people", "33,717 bills", "2,581,692 rows" (`u2-after.png`).
- **Up to 58em, the table is a list, as on a phone.** With its units, the Count column is wider,
  and the table was already wider than a tablet held upright. On dev, the page scrolled sideways
  from 721 to 803 pixels, and to 862 with the folds open. With the units alone it would have
  scrolled to 842, and an iPad at 768, 810, 820 or 834 pixels would have had to pan. The
  database's fold holds "person_numbers.person", which does not break, so with that fold open
  the table would have run past its box up to 926. Up to 58em (928 pixels), `/api`'s table is
  now laid out as it is on a phone (`u3-before-768.png` against `u4-after-768.png`).
- **Every width checked.** A sweep of every width from 302 to 1,440 pixels, folds shut and
  every fold open, finds no sideways scroll and no table past its box. Below 367 pixels the
  table scrolls a few pixels inside its own box, and below 342 the Download link runs past the
  screen's edge, exactly as on dev.
- **Printed,** a file's row of the list stays on one page.
- **Phones and the data page are unchanged.** The new rules apply to `/api`'s table alone
  (class `dpapi`), so the data page, which is live, is as it was: a reviewer compared 360 full
  screenshots of `/data` under dev's app.css and the branch's, and they are byte-identical. On a
  phone `/api` already showed its units and its list, and the phone screenshots before and
  after are byte-identical.

The site's code that changes is `api_page.py` and `app.css`.

## The shots

All are dry run 181's preview (`https://6502d18c.graniterecord.pages.dev/api`), taken on
6 November 2026. `u1` and `u2` show the table at 1280 pixels wide; `u3` and `u4` show the
screen at 768. For the after shots, the page's table was redrawn from the preview's own
`data/manifest.json` by this branch's `api_page.body`, and the branch's app.css was served in
place of the preview's. First, dev's `api_page.body` was run the same way: it reproduced the
preview's table byte for byte, so the after shots differ from the preview by this change alone.

## The check

Preflight's `_api_counts_say_units` holds:
- the cells and the head;
- the table's `dpapi`;
- app.css's list rule. There must be one top-level `@media (max-width:58em)` block, not
  commented out. Its every rule is a `.dpdl` rule of the phone block with `.dpapi` added,
  declaration for declaration, and nothing else, so no rule there can reach the data page, and
  a phone rule cannot change without its twin;
- the print rule.

It fails on dev. Each of 14 mutants turns it red: each part undone alone, the list nested,
commented out or missing a brace, a rule misspelt, deleted or without `.dpapi`, and a phone rule
changed without its twin.

## For whoever merges

`fix/movers-merge` (held for the owner) also takes `api_page.py` to `.8` and changes the people
row. The two changes do not overlap. Git keeps `.8` without a conflict, so whichever lands
second should take `api_page.py` to `.9` (`python3 src/ops/inventory.py --bump
src/pages/api_page.py`). preflight.py's stamp line and versions.json's preflight.py line do
conflict, loudly: take the higher number and add one.
