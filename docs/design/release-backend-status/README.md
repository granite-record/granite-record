# The release and backend session's board (session_01E3dVhbcYK2W3ZViQknFZyn)

Kept on the session's own branch, `dev-ioxv9i`, for the laptop manager, who reads branches with
`git fetch`. Cloud sessions cannot message it. This page is replaced, not appended to, and each
branch's latest commit message says its own status. Times are Eastern.

## As of Saturday 7 November 2026, about 10 a.m.

Received the laptop manager's messages of 7 November, through the one saying:
- dry run 2 (run 42368200550, dev e308cee5) is clean;
- dry run 3 (run 42372029110, dev d2a8e027) is running, as the release candidate for the
  owner's walk tonight;
- please write the walk list against dry run 2's preview.

### The owner's walk list: `docs/release-11nov.md`, rewritten

- Every stop was opened on dry run 2's own address, **https://4e2d47d7.graniterecord.pages.dev**,
  never the alias, and each says what that page showed.
- The second batch is folded into the stops where a reader meets it, not kept in a section of
  its own.
- The order is laptop first and phone last, so the window is resized once. There are ten
  sections, with times; sections 1 to 3 (★) are the twenty-minute walk.
- Dry run 3's one change, Leslie Feliciano as Strafford's District 1 commissioner, is a stop in
  section 5.
- **Corrected at about 10 a.m. after two checks of the list itself.** One fact-checked 104
  claims against dry run 2, dry run 183 and live. The other followed every stop literally, as
  the owner would.
  - Four statements were wrong, and are fixed:
    - the ★ walk is half an hour, not twenty minutes, and now includes dry run 3's stop;
    - Hart's Location typed on a laptop already worked on dry run 183, so it moved to the
      phone with O'Neil;
    - the directory lists all 34 people under one chamber, not eight (8 missing from the
      Senate list, 26 from the House's);
    - a plain Back, not a reload, leaves a bill drawn open in the list.
  - The rest were steps left out or words that mislead, and are fixed too: the folded
    proceedings.csv columns, the button names, closing a pane on a phone, the `?v=1` advice
    (it breaks an address with ? or #), and which stops only check an earlier dry run's slip.
  - Not taken: "seen by building the tab" in item 3 stands. This session built County
    Officials from d2a8e027's own code and corrections file, which the checker did not find on
    disk.

### Dry run 2 (dev e308cee5): the walk

**Nothing found holds the release.**

- **Every redirect rule: 631 of 631.**
- **Every stop of the walk list holds as written.** The list carries the exact words seen.
- **New from this walk:**
  - At phone width a record's pane (Cite, Testify) lies over the buttons below its own until
    it is closed. Dry run 183 does the same, and live does not. It is a nit.
  - `/bills#2020/HB703` shows the 2025–2026 list, on dry run 2 and on live. It does not open
    2025's bill, as the 3 a.m. list said. This is on live, for 24 November.
  - The status box on `/es/` has an English sentence that none of the new note's four reasons
    covers. Also on live.
- **For dry run 3, seen by building County Officials from d2a8e027's own code:**
  - Leslie Feliciano's row sits under the one source line for all 80 rows: "read from the
    Secretary of State's county roster for 2025–2026, dated December 5, 2024; read October 9,
    2026 … this is the roster read before it."
  - Her row comes from Strafford County's own list, read 6 November, and the roster names Joe
    Pitre.
  - `officials_tabs.county` never draws a row's own source.
  - A fix needs a Spanish line in `es.json`, which is not this session's to edit. It is in
    the walk list as "For you to decide", item 3.
- **Four deeper walks were still running at this commit:**
  - Back and the not-found page, every road in the branch's README;
  - every form the search branch claims, and 15 ordinary searches against dry run 183;
  - the Spanish note on every Spanish page;
  - regressions against dry run 183.

  Each finding is checked by a skeptic. Anything that survives follows in a commit of its own.

### Branches

| What | Branch | Status |
|---|---|---|
| The former-members directory lists a person who sat in both chambers under each | `fix/former-directory-both` 1c740815 | **READY**, offered on your word. It is dev d2a8e027 plus the fix, so it is in neither dry run 2 nor 3. Over dry run 2's `former.json`: 97 former senators and 1,688 former representatives, with 34 people under both. The search groups them 89 / 1,662 / 0. Under the other chamber a row has that chamber's title and its years first, with no party or seat ("Rep. Michael Downing R" would be wrong). Two reviews; every should-fix finding is fixed. `preflight --changed`: 915 passed, 0 failed, 76 skipped. Its README has before and after shots of dry run 183's page. Whether it rides this release or 24 November is the owner's call, in the walk list. |
| Back keeps the search; the not-found page finds the bill and the town | `fix/bill-back-notfound` c7d6041e | Merged by you into dev e308cee5, and walked on dry run 2. |

### Noted from your list for after this weekend

- **CORS for `schema.json` and `people.json`:** already in the release, as you say. Nothing to
  do.
- **Healthchecks noise** (task 28). From reading the code:
  - The preview sender reads `dry-run.graniterecord.pages.dev`. That has a changes file only
    on a night a dry run ran.
  - So at noon it raises `tonight` and pings `/fail` on any day it has been given a
    `HEALTHCHECK_URL`.
  - The plan:
    - the preview sender never pings (`ping()` returns early on a preview-only var in
      `[env.preview.vars]`);
    - the README's secrets table says `HEALTHCHECK_URL` is production's only;
    - a preflight check holds both.
- **The night-warnings check becomes "Night waiting for your approval"** (task 29). Only a
  warning that holds a night for approval pings it (`nightly.py`, `nightly.yml`).
- **After the webinar** (task 30), sample the two groups against the chaptered laws, and bring
  a fix with counts:
  - the 253 laws with a Law date before the Governor's;
  - the 1,618 with none.

  HB 703 of 2020 is one of the 253: its Law step is its effective date, Jan 1, 2020, before
  the Governor's Feb 10.

## Next

- **Today:** the four deeper walks of dry run 2. Any finding that survives its skeptic goes on
  this branch. The Back and not-found walk is done; its two candidates are being checked:
  - after Back, a term whose bills fail to load reads as having none;
  - an All Terms choice can be lost on a slow network, by Back, Forward, Back before the bills
    arrive.

  Both are rare roads and nits at most.
- **On your word:** `fix/former-directory-both`.
- **Monday:** the Videos wording.
- **After the weekend:** tasks 28 and 29; task 30 after the webinar.
- **24 November:**
  - night-clock, then lsr-accept;
  - the check_live mode that walks every redirect;
  - the tab-anchor follow-ups;
  - the HB 703 nits;
  - the bill search's tab title;
  - a sitting member's joined number answering 404 as JSON;
  - `careers.json`'s two same-chamber joins of namesakes;
  - Michael Downing's party per chamber;
  - the motion movers credited to namesakes (Seth King 2006, Butler 2014, Grossman, Schultz);
  - `/bills#2020/HB703`;
  - the phone-width pane;
  - the County Officials source line, if it does not go sooner;
  - the fix/bill-back-notfound deferrals in its README.
- **December:** outage recovery.
