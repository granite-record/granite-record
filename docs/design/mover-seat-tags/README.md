# A mover is named by the seat held that day

The follow-up the former-movers work named. On a House session day, a member
who later moved to the Senate was named without their seat: "Rep. Shannon
Chandley" where her 2009-2010 ballots give "(D - Hills 22)". A sitting mover
was drawn the same way: Sen. Cindy Rosenwald's House days said "Rep. Cindy
Rosenwald" with no seat.

The cause: a mover's page is kept under one number (Chandley's is 9404), and
the ballots of the earlier chamber are filed under the other one (568). The
session pages looked up the day's seat under the page's own number only.

The fix is in `fix/mover-seat-tags`:

- the joined rows of `legislators.json` and `former.json` now list
  `member_ids`;
- the session pages look up the seat under every number the page stands for;
- where two of the numbers hold a seat in the same term (a move in mid-term),
  the seat in the day's own chamber is used.

## The shots

These are of House, 3 March 2010, at 1280 and 390 pixels wide, before (dev
a53374b) and after (90116ee). The chip in question is outlined in red.

| | Before | After |
|---|---|---|
| Chandley, HB 1442 speaker | Rep. Shannon Chandley | Rep. Shannon Chandley (D - Hills 22) |
| Rosenwald | Rep. Cindy Rosenwald | Rep. Cindy Rosenwald (D - Hills 30) |

`1999-02-10-burling-1280-after.png` shows the second effect. The House
speaker lines of former movers had been plain words since the former-movers
merge folded their House pages away. They link again, with their seat: "Rep.
Peter Burling (D - Sull 19)". The before shot has no chip to frame, because
his name was plain text.

## What changed in the build

These figures compare full builds with `GRANITE_BUILD_DATE=2026-10-28`. The
baseline was built at two seeds, and the only file that differed was
`build.json`.

- 403 files differ:
  - 399 session-day files (319 House, 80 Senate, including 12 per-term JSON
    files);
  - `legislators.json` and `former.json`, which gain `member_ids`;
  - `data.html`, which now counts 1,102 checks, one more than before;
  - `build.json`.
- Over the 387 day pages that differ, compared chip by chip:
  - 173 chips of 16 movers gain their seat;
  - 379 speaker lines of 31 movers link again;
  - 4 chips are lost, all on 2015-03-11. "Rep. Long" there could be Douglas
    Long (R - Merr 4) or Patrick Long (D - Hills 23), since both sat that
    term. The old link was a guess, and the name now stays as words, as the
    rule for two members sharing a name says.
  - The Senate days change for the reverse kind of mover, members who sat
    in the Senate first and the House later (Ned Gordon, Amanda Merrill,
    Andrew Peterson, Fenton Groen, Frank Sapareto, Jacalyn Cilley). Their
    "Moved by" lines now link, with the Senate seat their earlier number
    holds, for example Gordon "(R - SD2)" in 1999.
  - Where a relinked member was excused, they are now counted in their
    party's figure. For example, on House 1999-01-28 the Republican figure
    goes from 28 to 29, and the total of 43 is unchanged.
  - Each page was diffed with member names, links and party figures
    normalized. After that, no page differs in anything else.
