# The release and backend session's board (session_01E3dVhbcYK2W3ZViQknFZyn)

Kept on the session's own branch, `dev-ioxv9i`, for the laptop manager, who reads branches with
`git fetch`. Cloud sessions cannot message it. This page is replaced, not appended to, and each
branch's latest commit message says its own status. Times are Eastern.

## As of Friday 6 November 2026, about 10:30 p.m.

Received the laptop manager's message of 7 November (Alice's decisions and the weekend plan), and
the one naming `fix/rollcall-date-line`.

### The weekend release

| What | Branch | Status |
|---|---|---|
| The candidate | `release/weekend` 3c79e70e | **In review; please do not move dev yet.** It is dev dd3f7ef9 plus the five branches below; preflight gives 995 passed, 0 failed. The laptop's full preflight can start now. A review of the merges and of how the branches meet is running, and a READY commit follows. |
| HB 703, the same page by other roads | `fix/bill-same-number-2` 91d4206b | In the candidate. |
| 1999-S-109's day, with Alice's line | `fix/rollcall-date-line` 6db56f00 | In the candidate, in place of `fix/rollcall-date`. |
| The 30 confirmed pairs, one person each | `fix/movers-merge` 8798a1a4 | In the candidate (Alice's yes). |
| `/api`'s counts say their units | `fix/api-units` b142ee31 | In the candidate. Ready: both reviews done. Every count says what it counts, and up to 58em the table is a list. 990 passed, 0 failed. |
| The deep walk's former-members regressions | `fix/movers-term` 04657c78 | In the candidate. Ready: both reviews done, and nothing blocks. 991 passed, 0 failed. |

### Not in the weekend release

| What | Branch | Status |
|---|---|---|
| HB 703 alone, for main | `hotfix/same-number-bills` 66e5a4a9 | Not needed: HB 703 rides in the release. Kept in case it slips past Sunday. |

## Next

- **Now:** the candidate's review. Then READY, with what is in and what is out.
- **Item (d):** which of the webinar deck's screenshots this release changes. A comparison of
  live and dry run 181's preview, slide by slide, is running.
- **After the dry run:** the deep walk of its preview, including the six senators of 1999–2000
  reading "1999 to 2000". Then Alice's walk list (release-11nov.md) under docs/.
- **24 November:**
  - night-clock, then lsr-accept;
  - the check_live mode that walks every redirect;
  - the tab-anchor follow-ups;
  - the HB 703 nits;
  - the bill search's tab title;
  - a sitting member's joined number answering 404 as JSON;
  - `careers.json`'s two same-chamber joins of namesakes (Pat Long and Patrick Long, the two
    Mark Pearsons). The cause is build_careers.py's bucket loop, which needs a one-chamber rule,
    rerun on the laptop with db/, plus a sitting member bounded by their own terms on session
    days. On live, 34 House days of 2007–2024 link the Patrick Long of Hills 26.
- **December:** outage-recovery.
