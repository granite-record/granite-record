# The release and backend session's board (session_01E3dVhbcYK2W3ZViQknFZyn)

Kept on the session's own branch, `dev-ioxv9i`, for the laptop manager, who reads branches with
`git fetch`. Cloud sessions cannot message it. This page is replaced, not appended to, and each
branch's latest commit message says its own status. Times are Eastern.

## As of Saturday 7 November 2026, about 3 a.m.

Received the laptop manager's messages of 7 November, through the one saying dry run 1 of dev
969c27fa is clean, with the edge-cache trap and the second batch.

### Dry run 183 (dev 969c27fa): the deep walk

Walked at the run's own deployment address, **https://dc501057.graniterecord.pages.dev**,
never the alias. Six lenses, each finding checked by a skeptic. The verdict: **nothing holds
the release.**

- **The three redirects: pass.**
  - `/legislator/frederick-king-sd-1` and `/legislator/leo-fraser-sd-4` answer 301 to the
    House pages, tabs and trailing slash included.
  - `/legislator/carl-johnson-sd-2` is SD2, 1999 to 2006. `/legislator/carl-johnson-sd-3` is a
    404 with no-store, with or without `?v=1`; the "1999 to 2009" seen on the alias was its
    cache.
  - Each joined number's JSON answers 301 to the page's own file.
- **The joined pages: pass.** All 34 answer 200. Each names both chambers with its years, in
  the head, the meta, the On Record line, the directory and the site search.
- **The six senators of 1999–2000: pass.** Each reads "1999 to 2000" on the page, in the meta,
  in find.json, in former.json and in the directory. 1999-S-109 is on 22 October 1999
  everywhere.
- **people.json: pass.** The 30 pairs are one person each, Pierce stays two, and /api says
  "2,157 people".
- **HB 703 by every road: pass.** No step mixes the two bills: All Terms, open 2020, a new
  search typed while it is open, Back, each bill's address and tabs. The known Back fault is
  there, as expected; fix/bill-back-notfound's app.js served in place fixes it on this
  preview.
- **Every redirect rule: 631 of 631.** All 121 recorded moved addresses were tried too.
- **No regression against dry run 181 or live.** 26 pages were compared in English and
  Spanish at both widths. There were no script errors, and the headers, robots and feeds were
  checked. The sitemap's only changes are the three swaps.
- **Dry run 181's 26 confirmed findings:**
  - Fixed: the blocking one (session days giving a joined member's other-chamber days to a
    namesake), and ten should-fix ones (items 1–9 and 15).
  - Partly fixed: item 10. The spans are right; the two residuals are below, for a decision.
  - Still there:
    - item 11 (the tab title), which is on live;
    - item 13 (Back), which is fixed in dry run 2;
    - the nits, listed in the walk list.

**For a decision**, both new with the release, from the 30 joins:
1. `/directory/former-legislators` lists each joined person under one chamber only. Eight who
   sat in the Senate are under the House alone, so the count reads 89 former senators and
   1,662 former representatives, where the record has 97 and 1,688.
   - The cause is `former_page()` in `build_indexes.py`.
   - The fix is small: list each joined person under each chamber. It can be ready for dry
     run 2 on your word.
2. Michael Downing's one page calls him a Republican throughout. He was a Democrat in the
   House, 1999–2002.
   - He is the only pair whose party differs between chambers.
   - The fix needs a party for each chamber's years. It is larger, and suits 24 November.

**The owner's walk list** is `docs/release-11nov.md` on this branch. It was written fresh,
since no branch carried the old one. It has every reader-visible change since live, from the
release's commits, each opened on the dry run, and the second batch marked "dry run 2". It
gives the deployment address to walk.

### The second batch, for dry run 2

| What | Branch | Status |
|---|---|---|
| Back keeps the search; the not-found page finds the bill and the town | `fix/bill-back-notfound` c7d6041e | **READY** (2:36 a.m.). It is release/weekend with dev 969c27fa merged in, plus the fix. Three reviews, each finding verified, and every should-fix and blocking finding fixed. Preflight: 996 passed, 0 failed, 130 skipped; `--changed` 909 passed, 0 failed. 48 of 49 mutants turn red; the 49th undoes a guard the harness cannot time. A browser walk on dc501057 matches its README. The status count is there: 253 of 12,106 laws have a Law date before their signing, and 1,618 have none. |

### Not in the weekend release

| What | Branch | Status |
|---|---|---|
| HB 703 alone, for main | `hotfix/same-number-bills` 66e5a4a9 | Not needed: HB 703 rides in the release. |

## Next

- **On your word:** the directory fix, for dry run 2.
- **After dry run 2:** a walk of its own address. Its first lens is the second batch's merges.
- **Monday:** the Videos wording.
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
  - `/bills#2020/HB703` opening the newest term's bill;
  - the fix/bill-back-notfound deferrals in its README.
- **December:** outage-recovery.
