# For the owner to paste: nine seats in `member_corrections.json`

These nine entries in `corrections/member_corrections.json` (`"members"`)
set a seat by hand. Nothing generated overrides them, so a former member's
page shows the seat written here.

The page shows the seat of the member's **last** term. That seat is built
from `county` and `district`, so `district` has to be a bare number.

- **Six entries write a history in `district`**, e.g. "25 for 2007-2012;
  Hillsborough 34 after the 2012 redistricting". The seat can't be read from
  it, so the page shows **no seat** at all.
- **Three entries give a number, but it isn't the last term's seat.**
  Christie, Rowe and Balcom each give the seat of their first term.

Session days no longer need a seat history in this file. Since 5 November
2026 they take each term's seat from that term's bills (`term_seats`). So
each edit below:
- sets `district` to the number the member's last-term bills print;
- moves the history into a new key, `seat_note`, which the build doesn't
  read.

Each **Evidence** line gives the bills of that term that print the member's
sponsor line (from `text_sponsors.json`, each bill's own printed text), with
the line as printed. Nothing else in any entry changes.

**How to paste:** in each entry, replace the `"district"` value as shown, and
add the `"seat_note"` line after it. Keep the commas as JSON needs them.

---

## 374900, Christie, Andrew, Jr. (last term 2015-2016)

The entry today has `"district": "22"`. That is his 1999-2000 seat.

```json
"district": "37",
"seat_note": "Rockingham 22 in 1999-2000 (20 bills: 'Rep. A. Christie, Rock 22'); Rockingham 37 in 2015-2016 (9 bills, e.g. HB 464, SB 57, HB 1122: 'Rep. A. Christie, Rock 37')",
```

**Evidence (2015-2016):** 9 bills, every one "Rock 37".

## 376192, Rowe, Robert H. (last term 2015-2016)

The entry today has `"district": "14"`. That is his 1999-2002 seat.

```json
"district": "22",
"seat_note": "Hillsborough 14 in 1999-2002; 47 in 2003-2004; 6 in 2005-2012; 22 in 2013-2016 -- each as that term's bills print it ('Rep. Rowe, Hills N')",
```

**Evidence (2015-2016):** 11 bills (HB 204, HB 631, SB 14, ...), every one
"Hills 22". The same holds for 2013-2014 (11 bills).

## 376302, Balcom, John L. (last term 2015-2016)

The entry today has `"district": "18"`. That is his 2001-2002 seat.

```json
"district": "21",
"seat_note": "Hillsborough 18 in 2001-2002; 58 in 2003-2004; 21 in 2015-2016 -- each as that term's bills print it ('Rep. Balcom, Hills N')",
```

**Evidence (2015-2016):** 20 bills (HB 296, HB 461, HB 512, ...), every one
"Hills 21".

## 376716, Hogan, Edith (last term 2015-2016)

The entry today has `"district": "25 for 2007-2012; Hillsborough 34 after the 2012 redistricting"`.

```json
"district": "34",
"seat_note": "Hillsborough 25 for 2007-2012; Hillsborough 34 after the 2012 redistricting",
```

**Evidence (2015-2016):** 14 bills (HB 489, HB 655, CACR 17, ...), every one
"Hills 34". 2007-2012 print "Hills 25" (30 bills), as the entry says.

## 376728, Wheeler, Deborah (last term 2015-2016)

The entry today has `"district": "6 for 2007-2010; Merrimack 3 after the 2012 redistricting"`.

```json
"district": "3",
"seat_note": "Merrimack 6 for 2007-2010; Merrimack 3 after the 2012 redistricting",
```

**Evidence (2015-2016):** 8 bills (HB 461, SB 53, SB 90, ...), every one
"Merr 3".

## 376750, Devine, James (last term 2015-2016)

The entry today has `"district": "7 for 2007-2012; Rockingham 4 after the 2012 redistricting"`.

```json
"district": "4",
"seat_note": "Rockingham 7 for 2007-2012; Rockingham 4 after the 2012 redistricting",
```

**Evidence (2015-2016):** 7 bills (HB 391, SB 208, HB 1303, ...), every one
"Rock 4". The same holds for 2013-2014 (6 bills).

## 377020, Schroadter, Adam (last term 2015-2016)

The entry today has `"district": "12 in 2011-2012; 17 in 2013-2014 and 2015-2016 (...)"`.

```json
"district": "17",
"seat_note": "Rockingham 12 in 2011-2012; 17 in 2013-2014 and 2015-2016 (the 2012 redistricting renumbered the seat)",
```

**Evidence (2015-2016):** 27 bills (HB 237, HB 283, HB 354, ...), every one
"Rock 17".

## 377028, Simmons, Tammy (last term 2015-2016)

The entry today has `"district": "17 in 2011-2012; 17 again in 2015-2016 under the new plan"`.

```json
"district": "17",
"seat_note": "Hillsborough 17 in 2011-2012; 17 again in 2015-2016 under the new plan",
```

**Evidence (2015-2016):** 21 bills (HB 311, HB 389, HB 406, ...), every one
"Hills 17".

## 377048, Ward, Joanne (last term 2015-2016)

The entry today has `"district": "13 in 2011-2012; 19 in 2015-2016 (bill text, ...single-sourced)"`.

```json
"district": "19",
"seat_note": "Rockingham 13 in 2011-2012; 19 in 2015-2016",
```

**Evidence (2015-2016):** 20 bills (SB 23, SB 71, HB 1204, ...), every one
"Rock 19" ("Rep. J. Ward, Rock 19"). The entry's "single-sourced" note no
longer holds: it is 20 bills.

---

**After pasting:** the next build shows each page with its seat, and the
address moves with it. For example, Edith Hogan's page moves to
`/legislator/edith-hogan-hills-34`. The build does **not** make redirects
for addresses that move because of a correction; an address that existed
would need one.

Today's addresses for the six with no seat end in the bare name (e.g.
`edith-hogan`), because `member_slug` has no district to add. If the
addresses should not move, say so before pasting, and I'll add redirects for
these nine on the branch.
