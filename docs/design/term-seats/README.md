# The seat held at the time, from the bills of the time

## The problem

On past session days, a member was often named with a seat they did not
hold that day.

A ballot's label is not dated. A former member's label is built from one
record of their seat (`build_data._former_label`), and that is the seat they
last held. So Shannon Chandley read "Hills 22" on her 2009-2010 ballots. That
is the seat she took in 2016; every bill she sponsored in 2010 prints
"Hills 6".

`term_seats` read those labels as "the seat held at the time". The bill cards'
sponsor lines take each member's seat from the bill's own text, so on 274
session days the same member was named at two seats: one in the sponsor line
and another as a speaker.

## The rule

`build_site_v2.term_seats` now gives each member number a seat for each term:

1. **The bills' seat.** If the term's bills print one seat for the member,
   that seat. This comes from `text_sponsors.json`, by the rule
   `build_data.date_ballot_seats` already used for sitting members.
2. **The last-term record.** Otherwise, only in the member's last term, the
   seat their ballots give: today's roster for a sitting member, or the
   corrected record of where a former member last sat. It is refused where
   the term's bills say otherwise:
   - the bills print the member at two seats; or
   - a sponsor line of the member's surname, in their chamber, is at another
     seat, and `text_sponsors` placed that line on no one. One example is
     Winston McCarty in 1999-2000: the record says Merr 10, and three bills
     say Hills 38.
3. **No seat.** Otherwise the member is named with no seat. No source, no
   seat.

A seat is only ever the day's chamber's: a seat in the other chamber is never
the one held on that chamber's day.

What is shown is kept apart from who voted. The floor record carries both:
- `seats`, the seat shown on the page;
- `ballots`, who voted in each term, which is the old map. It is used only to
  link a name that no roster matches.

As a result, no link on any page moved.

## Measured

The yardstick is an independent join of the bill texts
(`db/past/PastLegislationText.jsonl`) to `PastSponsors`' member numbers. It
is a different route from `text_sponsors`, which places sponsors by surname.

| | Agrees with the join |
|---|---|
| New seats | 4,633 of 4,633 (every seat the join can test) |
| Old seats | 3,113 of 4,631 |

Before, 6 of the 13 last-term seats the join could test were contradicted.
Now the 6 that can still be tested all agree.

Two further measures:
- Within one term, one year's bills predict the other year's district
  3,555 times in 3,558 (prototype).
- Where the former-members record and the bills both say, the record's
  last-term seat is the bills' seat 1,439 times in 1,517. Its misses are
  errors in the record itself, such as "Rock 73" or "Straf 69".

## The build

Full builds, `GRANITE_BUILD_DATE=2026-10-28`. The baseline (dev 7e73aae) was
built at seeds 1 and 2, and the two differed only in `build.json`.

528 files differ:
- 526 session-day files (484 House, 42 Senate);
- `data.html`, which counts two more checks;
- `build.json`.

On the 516 day pages that differ:

| Change | Count |
|---|---|
| Chip seats changed | 7,659 |
| Chip seats dropped (no source) | 943 |
| Chip seats added | 34 |
| Seats changed in sentences (presided, moved by) | 1,375 |
| Seats dropped in sentences | 134 |
| Seats added in sentences | 6 |
| Links gained or lost | 0 |

The pages also lost a lower-casing bug: "rep. frederick andrews (r - hills
34) led the pledge of allegiance" appeared on 10 days.

With member seats and the Pledge's case normalized, no page differs.

Days naming one member at two seats went from 274 to 1. The one left is
Schultz on 2023-02-22, where a bill carried over from 2022 names the seat it
was filed under.

The chip check (`_session_chips_seat_of_their_term`) used to pass on nothing,
because its pattern wanted ".html" links. It now passes on the real pages:
- 25,749 chips and 10,126 names in sentences are named by the seat of their
  term, or by none;
- 33,649 sponsor lines agree with it.

## The shots

House, 3 March 2010, at 1280 and 390 pixels wide, before (`tsbefore`) and
after (`tsafter`):
- Before, Chandley is "Hills 6" as HB 1387's sponsor and "Hills 22" speaking
  on HB 1442.
- After, she is "Hills 6" in both places, and Baldasaro is "Rock 3" in both
  places.
