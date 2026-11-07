# The weekend release (release/weekend)

The release and backend session built this for the laptop manager on Friday 6 November 2026, at
about 10:30 p.m. Eastern, as asked in its message of 7 November. Alice's decisions of 6 November,
9:30 p.m., set what is in it.

**Dev is not touched.** The laptop runs the full preflight (with the data checks, since the kit
is there), moves dev to this branch, and starts the dry run.

## What is in

The branch is dev `dd3f7ef9` (the 11 November candidate of dry run 181) with five branches
merged. Every merge conflict was a version stamp, set one past the higher.

| Branch | Head | What a reader sees | Screenshots |
|---|---|---|---|
| `fix/bill-same-number-2` | 91d4206b | HB 703, and every bill number two terms share, opens in its own term from the All Terms search, by Back after a search, from a direct address, after a glossary tooltip is clicked, from a history jump, and on the Bill Text tab. It rides here in place of the hotfix to main. | `docs/design/same-number-bills/` c5 to c10 |
| `fix/rollcall-date-line` | 6db56f00 | Roll call 1999-S-109 reads 22 October 1999, as Alice's line in `corrections/rollcall_corrections.json` says. The six senators who sat only in 1999–2000 then read "1999 to 2000", not "to 2009". | none: the dry run shows it |
| `fix/movers-merge` | 8798a1a4 | `people.json` gives each of the 30 confirmed same-person pairs as one person (Alice's yes). `/api`'s people count counts people. | `docs/design/movers-merge/README.md` sets out the 30 |
| `fix/api-units` | b142ee31 | `/api`'s counts say what they count ("14 tables", "43 files"), and up to 58em its table is a list, as on a phone. The data page is unchanged. | `docs/design/api-units/` u1 to u4 |
| `fix/movers-term` | 04657c78 | A former member's last vote is taken by term, so King and Fraser keep their House pages and Carl Johnson stays at SD2. Joined pages name each chamber with its years. A joined number's JSON redirects. Session days no longer give a joined member's other-chamber days to a namesake (the deep walk's blocking finding). | `docs/design/movers-term/` m1 to m5 (before; the dry run shows after) |

Version stamps on this branch: preflight.py `.786`, api_page.py `.9`; every other file is at its
branch's stamp.

## What is out

- **After the webinar:** live/session, and the Videos wording.
- **24 November:**
  - night-clock, then lsr-accept;
  - the check_live mode that walks every redirect;
  - the tab-anchor follow-ups;
  - the HB 703 nits;
  - the bill search's tab title on an opened bill (also on live);
  - a sitting member's joined number answering 404 as JSON (also on live);
  - `careers.json`'s two same-chamber joins of namesakes (Pat Long and Patrick Long, the two
    Mark Pearsons; also on live). The fix is in build_careers.py and needs the laptop's `db/`.
- **December:** outage-recovery.
- **No longer needed:** `hotfix/same-number-bills`. HB 703 rides here; if the release slips
  past Sunday, the hotfix is still there.

## Checked here (the cloud, without the kit)

Preflight on Python 3.14: 995 passed, 0 failed, 130 skipped (the data checks).

## For the dry run and the deep walk

- The six senators of 1999–2000 (John King, Richard Russman, James Squires, Mary Brown,
  Patricia Krueger, Rick Trombly) read "1999 to 2000", and 1999-S-109 sits on 22 October 1999.
- King and Fraser are on their House pages, and their Senate addresses redirect there.
- `people.json` has one person for each of the 30 pairs, with the right page.
- `/api`'s table is a list from 721 to 928 pixels.
- HB 703 under All Terms, by every road above.
