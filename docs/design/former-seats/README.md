# A former member's page: the seat their last term's bills print

## The problem

A former member's page took its seat from one record of where they last sat:
`former_members.json`, through `build_data._former_label`. A fetch fills
that record from the General Court's current-state view.

Against the bills of the member's last term, the record was wrong on 76
pages:
- 75 House pages, of the 1,468 where those bills print one seat;
- one Senate page, Carl Johnson's, SD 2 where his bills print SD 3.

Ten of the record's seats are districts the map never had. Rebecca
Hutchinson's 1999-2000 seat was "Rock 73", in a county the 1992 map numbered
only to 36. Her bills print Rockingham 8.

## The fix (`fix/former-seats`, off `fix/term-seats`)

- **The bills' seat.** `build_site_v2.date_former_seats` gives the page the
  seat its member's last term's bills print, where they print one in the
  member's chamber.
- **What it leaves alone.** A seat the person set in
  `member_corrections.json` stands as written; the file is read, never
  written. `_former_label` and the ballot labels are left alone, because
  member_links decides joins from them.
- **The address moves.** The page address is built from the seat, so it
  moves. The old address goes in the row's `moved_from`, and `build_pages`
  answers it with a 301, in three forms.
- **Collisions.** A move onto an address that a page or a 301 already
  answers is not made, and the build says so. That covers former members,
  sitting members, and earlier moves.
- **Permanent 301s.** `generated/moved_addresses.json` keeps every address
  ever moved from: these 76, and the 34 earlier pages of members who moved
  between chambers and have left, 110 in all. `src/ops/record_moves.py`
  merges each build's moves in and never drops or re-points one. Every
  build reads the file (`keep_moved`) and says what it moved that isn't
  recorded. Preflight holds that only `record_moves.py` writes the file and
  that it only grows.

## Proof

Full builds with `GRANITE_BUILD_DATE=2026-10-28`. The base is fix/term-seats
c25043a (manifest `tsend`, seed 1). The fix was built at seed 1 (25221aa)
and seed 2 (b4b66bd); the two differ only in `build.json` and `data.html`.

**3,545 files differ.** Each kind was checked:
- **3,292 files:** with every moved address put back to the old one, the
  file hashes **exactly** to the base build's manifest. The only change is
  the address.
- **76 pages are new and 76 are gone:** the moved pages, under their new
  addresses.
- **The rest:** the 76 per-member data files with the new seat; 18 export
  files (`data/*.jsonl.gz`) carrying the addresses and seats;
  `former.json`; the directory; `find.json`; one bill (2023 HR 8, whose
  sponsor David Cote now reads "Hills 31", as his bills print);
  `_redirects`; `data.html` (one check more); `build.json`.

`_redirects` now holds 602 rules, against Cloudflare's limit of 2,000.
Preflight's redirect checks pass on the built site, including "no redirect
stands over a page".

## Not done

- **Two impossible districts remain,** because no bill of the member's last
  term prints their seat: P. Judith Sullivan (Merr 39, 2001-2002) and
  Carlos Gonzalez (Hills 48, 2015-2016). No source, no seat change. They are
  listed in `MOVED.md`.
- **Nine members with an owner's correction** are untouched. Six of them
  show **no seat**, because their `district` holds a sentence.
  `OWNER_PASTE.md` drafts the edits, with each one's evidence, for the owner
  to paste.

## Files here

- `MOVED.md`: the 76 moves, old address and new, and the ten impossible
  districts.
- `OWNER_PASTE.md`: the nine owner edits.
- Shots at 390 and 1280 pixels wide:
  - Rebecca Hutchinson: "Rockingham District 8", was Rock 73.
  - David Cote: "Hillsborough District 31", was Hills 3.
