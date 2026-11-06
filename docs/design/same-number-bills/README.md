# Two bills of one number stay two (for 11 November)

The branch is `fix/bill-same-number`; the same change to `app.js` is on
`hotfix/same-number-bills`, from main, for the live site alone if the 11 November update cannot go
first. The owner found it on 6 November 2026.

With All Terms chosen on the bill search, HB 703 is two bills: 2020's on prescription drugs (Rep.
Edward Butler; Chapter 4, Laws of 2020) and 2025's on school meals (Rep. Hope Damon). The list knew a
bill by its number, and with every term's bills loaded the number named both. Clicking the "HB
703-FN (2020)" result opened 2025's bill at `/bill/2025/hb703`; and where 2019–2020's bills had
loaded first, the page showed 2025's heading over 2020's record, rail and summary, with no Testify,
which is what the owner saw.

Now the bill a reader clicks opens in its own term, the one its link names, as a bill's own
address already opened it; the term the reader chose (All Terms) is held and put back when the bill
is closed, as the Term control's choice already was while a bill is open. Back and Forward reopen
the same bill.

## How the shots were made

Each shot is `<item>-<bill>-<before|after>-<390|1280>-<light|dark>.png`: the live site,
graniterecord.org, on 6 November 2026, at `/bills?q=HB703`, All Terms chosen, the "(2020)"
result's number clicked. **Before** is the site as it served; **after** is the same site with this
branch's `app.js` served in place of its own, so the bills are the real ones.

## 1. The "(2020)" result, a desktop (`c1`, `c2`)

`c1`, before: the address is `/bill/2025/hb703` and the page is 2025's HB 703-FN-A-LOCAL, school
meals, Rep. Hope Damon, 2025–2026 Term. `c2`, after: `/bill/2020/hb703`, 2020's HB 703-FN,
prescription drugs, Rep. Edward Butler, Chapter 4, Laws of 2020, 2019–2020 Term. The picker still
reads All Terms.

## 2. The same click on a phone (`c3`, `c4`)

The same, at 390 pixels.

Not shown, and checked the same way: Back returns to the All Terms list of every HB 703 (ten
terms have one), and clicking the 2025 result then opens 2025's bill. The owner's case, 2025's
heading over 2020's record, is reproduced in preflight's `_same_number_one_bill`, which draws the
page in node from either term's bills arriving first.
