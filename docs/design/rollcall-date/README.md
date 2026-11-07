# A roll call's day, put right by the owner (held for the owner's word)

The branch is `fix/rollcall-date`, from dev `dd3f7ef9`. The deep walk of dry run 181 found it on
6 November 2026.

**Status: held.** The code is done, and preflight passed: 990 passed, 0 failed. It does nothing
until the owner adds the line below to their file. It can be merged before or after they do: with
no `misdated` entry, nothing changes.

## What is wrong

Roll call **1999-S-109** is dated 22 October **2009** in the General Court's roll-call file
(`records/rollcalls/RollCallSummary_1999.txt`):

```
1999|S|108|10/22/1999 12:00:00 AM|CACR16|17|6|23|0|||Order to 3rd Reading3/5 Necessary|…||10/25/1999 10:29:09 AM
1999|S|109|10/22/2009 12:00:00 AM|CACR17|15|8|23|0|||Order to 3rd Reading3/5 Necessary|…|10/25/1999 10:26:07 AM
1999|S|110|10/22/1999 12:00:00 AM|CACR16|12|9|23|0|||Final Passage3/5 Necessary|…||10/25/1999 10:26:57 AM
```

What the record says about it:

- **CACR 17's own docket** dates the vote 22 October 1999: "Sen Brown Floor Amendment {2165} New
  Title, AA, VV Ot3rdg, (3/5 Necc) RC (15Y-8N), MA". That is this roll call: Order to 3rd
  Reading, three fifths necessary, 15 to 8.
- **The roll call's own last field** says it was entered on 25 October 1999 at 10:26 AM, the
  same morning as 108 (10:29) and 110 (10:26:57). Both of those are dated 22 October 1999.
- **Every other ballot is dated within its term.** This is the only one of 2,303,047.

What a reader sees today:

- CACR 17's Votes tab shows the vote on 22 October 2009.
- The 23 senators who cast it have it as their newest vote on their own Votes tabs.
- The six who sat only in 1999–2000 read "served in the New Hampshire Senate, 1999 to 2009":
  John King, Richard Russman, James Squires, Mary Brown, Patricia Krueger and Rick Trombly.

## What the branch does

`corrections/rollcall_corrections.json` could move a roll call to another bill (`misfiled`), but
not to another day. The branch reads a second section, `misdated`, in the same way:

- An entry is keyed by the roll call as the site names it.
- It gives the day the file gives (`says`) and the day it was (`is`), both m/d/Y, with the
  evidence.
- It is applied only while the file still gives the day it says. An entry that has stopped
  matching is reported and not applied, and preflight fails on it.
- `rollcall_parser.roll_call_when` reads it wherever a roll call's day is read beside its bill:
  `rollcalls.json`, every ballot (`build_data`) and the floor index.

Preflight's `_rollcall_misdated` holds it on a made-up project, and against the owner's own file
once there is an entry.

## The owner's line (theirs to add; this branch does not touch the file)

Add beside `"misfiled"` in `corrections/rollcall_corrections.json`:

```json
  "misdated": {
    "1999-S-109": {
      "says": "10/22/2009",
      "is": "10/22/1999",
      "evidence": "CACR 17 (1999)'s docket dates the Senate's 15-8 roll call to order it to third reading (Sen. Brown's floor amendment 2165, three fifths necessary) 22 October 1999; the roll-call file entered it on 10/25/1999 10:26:07 AM, the morning it entered 1999-S-108 and 1999-S-110, both dated 10/22/1999; it is the only ballot of 2,303,047 dated outside its term.",
      "checked": "2026-11-07"
    }
  },
```

The Senate Journal of 22 October 1999 would be stronger evidence still, if the owner has it to
hand.

## Not covered

`build_careers` and `score_members_elect` read the day from the database dump and from the
files on their own. Both take a vote's term through `proceedings.vote_term`, which already puts
1999-S-109 in 1999–2000, so neither is wrong because of it. `fix/movers-term` stops the date
choosing anybody's page or seat in any case. This branch only puts the day right where it is
shown.
