# The release and backend session's board (session_01E3dVhbcYK2W3ZViQknFZyn)

Kept on the session's own branch, `dev-ioxv9i`, for the laptop manager, who reads branches with
`git fetch`. Cloud sessions cannot message it. This page is replaced, not appended to, and each
branch's latest commit message says its own status. Times are Eastern.

## As of Friday 6 November 2026, about 9 p.m.

### Waiting on the owner

| What | Branch | Status |
|---|---|---|
| HB 703 for the live site, alone | `hotfix/same-number-bills` 66e5a4a9 | **Ready for main on the owner's word.** Main a0354996 plus the HB 703 fixes, app.js and preflight only. 959 passed, 0 failed. Dry run 182 (of the earlier 9f964f13) never started: "the night" was given no runner, almost certainly the "preview" environment's branch rule (only dev and main have ever run it). Either admit the branch there and dry-run it, or put it on main: the night then holds for approval, since its code differs from production's. |
| The 30 confirmed pairs, one person each in people.json | `fix/movers-merge` 8798a1a4 | **Held for a yes or no** (default yes). Its README sets out the 30 merges. If no, drop it, and word the API page and people.json to list the pairs separately. |
| 1999-S-109's date | `fix/rollcall-date` 0e1a568a | **Held, safe to merge.** The owner's file can now correct a roll call's date. The line for 1999-S-109 is drafted in its README for the owner to paste; their file stays theirs. |

### Ready to merge into dev

| What | Branch | Status |
|---|---|---|
| HB 703, the same page by other roads | `fix/bill-same-number-2` 91d4206b | **Ready.** Fixes the search then Back, a direct address, a glossary tooltip click, the Cite row on a history jump, a record arriving after Back, and the Bill Text tab. Both reviews done, 989 passed and 0 failed. |

### In progress

| What | Branch | Status |
|---|---|---|
| The deep walk's former-members regressions | `fix/movers-term` | Each former member's last vote is taken by term. That keeps King and Fraser on their House pages and Carl Johnson at SD2. It also covers the descriptions, the directory and search lines, the JSON 301s, and the session days that named a namesake (blocking). Its two-lens review is running. A commit with the review's result follows. |

## Dry run 181 (dev dd3f7ef9, the 11 November candidate)

The run was clean. Preview: https://6502d18c.graniterecord.pages.dev

**Redirect walk.** All 602 checks of `_redirects` were correct on the preview. 587 old addresses
redirect to the right page, and 15 rewritten addresses serve the target's page.

**Deep walk.** Five lenses (the record, links, words, access, regressions against live), each
finding checked by a skeptic. The confirmed findings:

- **Blocking: session days named the wrong member** where a joined former mover shares a surname
  (Seth King for Frederick King, Cassandra Levesque for Melanie Levesque, Paula Bradley for Jeb
  Bradley, Marilyn Fraser for Leo Fraser; 44 days). Fixed on `fix/movers-term`
  (`_joined_mover_session_days`).
- **Should-fix, regressions, fixed on `fix/movers-term`:**
  - King and Fraser were kept as "Former Senator", and their live House addresses redirected there.
  - Carl Johnson was moved to SD3.
  - The joined pages' descriptions put the whole career in one chamber.
  - So did their directory lines and their site-search rows.
  - The JSON of each joined member's second number answered 404.
- **Should-fix, on `fix/movers-merge` (held):** people.json gives each of the 30 confirmed pairs as
  two people.
- **Should-fix, on `fix/rollcall-date` (held):** 19 former senators read "1999 to 2009". 13 of them
  are put right by `fix/movers-term`; the other 6, who sat only in 1999–2000, wait for the owner's
  line.
- **Should-fix, not on any branch yet:**
  - `/api`'s ROWS column hides its units at desktop widths, so it reads "14" for the database and
    "43" for the manifest. `.dpu{display:none}` sits outside the media query in app.css. `/api`
    is new in this update (it answers 404 on live), so readers would meet this new.
  - Opening a bill from the bill search leaves the tab titled "New Hampshire Bills — search every
    bill since 1989", with focus on the search box. Live does the same.
- **Nits, for 24 November:**
  - `/live` is linked from no page; a known deferral, PATCHES 2 and 3.
  - A voice vote's date links to an anchor its session day lacks.
  - Back from a bill drops `q=` from the address, and Forward is lost.
  - An action pane stays open when Tab leaves it; the same on live.
  - Three joined movers' heads abbreviate the county ("Straf District 6").
  - `/api`'s code boxes have no inner padding.
  - A law page's Follow pane opens far from its button.
  - Former members' headings mix short and full county names.
  - `/api` writes field names as prose.
  - An ungrammatical CACR 21 sentence in the register of probate FAQ.
  - Session-day chips title-case "And".
  - English county cards don't say the district lists are in the statute's words.

The skeptics refuted the rest:
- Live Now's check time;
- the rights wording on /data;
- How to Vote's "may change again";
- CACR 13's outcome: its count is not in `corrections/ballot_results.json` yet;
- the Strafford vacancy: none on file.

The record lens checked many things and found them right:
- the manifest, the counts and the sha256 of every download;
- all 119 recorded former addresses;
- the 84 session days sampled for seats;
- all 80 county officers;
- the same-number bills;
- the committee pages.

## Next, unless the laptop manager says otherwise

- Finish `fix/movers-term`: the review's findings, then mark it ready.
- **Monday 9 November:** the Videos wording, for Monday's second dry run.
- **24 November:**
  - night-clock, then lsr-accept;
  - the check_live mode that walks every redirect;
  - the tab-anchor follow-ups;
  - the HB 703 nits above.
- **December:** outage-recovery.
