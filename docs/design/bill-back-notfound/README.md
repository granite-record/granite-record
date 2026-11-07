# Back keeps the search; the not-found page finds the bill (for the weekend release)

The branch is `fix/bill-back-notfound`, on top of `release/weekend`, for the second dry run. The
laptop manager's browser test of 7 November 2026, on dry run 181's preview, found these. Two
reviews of the fix found more on the same roads. All of them are on live too, except where a
line says the branch made it.

## Back from a bill keeps the search

**What was wrong.** On `/bills`, with All Terms chosen, search HB 703, open a result, then press
Back. The list showed the search's results, but the address had lost its words:
`bills?q=HB+703&term=all` became `bills?term=all`. A reload or a shared link lost the search,
and Forward no longer reached the bill. Back had put the list's own address back, and the page
then pushed a bare `/bills` over it.

**What it does now.**
- On Back the page pushes nothing, and Forward reopens the bill.
- The list is drawn as its own entry's address names it: its words, its term, every filter
  ticked and its order, as the list wrote them there. The box, the list and the address agree.
- If the reader turned the term picker while the bill was open, that choice still stands, as it
  did before.
- **Back twice** (the first review): from a later list of another search and term, past the
  bill, to the first list. That drew the first list's words in the later list's term, which
  nobody had seen. It now draws the first list as it was.
- **Reload a bill, then Back** (the first review): the page sent the reader to bare `/bills`,
  the newest term with an empty box. This is the likeliest road to the empty box the manager
  saw. The page now loads the address Back put back, words and term, and opens it where the
  reader stood in the list (the second review).
- **"Back to search results"** on a bill that an address opened over the search
  (`/bills?q=…#2020/HB703`) keeps the search's words too.

**The second review's findings, fixed here.**
- **Two topics, then Back** (the branch made this one): Back kept only the first of two ticked
  topics, and wrote the shorter address over the list's. Every topic the address names is read
  now, on Back and when the page loads. On live a page loaded at a two-topic address already
  lost the second.
- **A term asked for twice** (the branch made this one): with a bill open, the picker turned
  to a term whose bills had not arrived, then Back at once, asked for them twice and drew every
  bill of that term twice. Each term is asked for once at a time now, and Back says "loading…"
  while it waits, as the picker does.
- **Back twice to a list of no words**: the later search's words stayed in the box over the
  first list (`/bills?status=Passed`, then "dog" from a bill, then Back twice, read "dog"). The
  same happened to words typed and never run. A list's address names its words only where a
  search was run. So the list now keeps the words it was left with in its own history entry,
  and Back draws them.
- **Nothing left to try**: a search of every term that finds nothing no longer says "Try
  removing a filter, or a different term" where no filter is ticked and All Terms is chosen.

A browser walk on dry run 183's own deployment (dc501057), the branch's app.js served in place
of its own:

| Road | Dry run 183 (and live) | This branch |
|---|---|---|
| Search HB 703 in All Terms, open 2020's, a new search typed, Back twice | `/bills?term=all`, the later search's list | `/bills?q=HB+703&term=all`, box "HB 703", 10 bills |
| Then Forward | the bill is gone | `/bill/2020/hb703` |
| Two topics, open a bill, Back | one topic at load, 250 bills | both topics, 289 bills, Back and Forward alike |
| `/bills?status=Passed`, a bill, "dog", Back twice | box "dog", 10 bills | box empty, 686 bills |
| "school meals" typed, not run; a bill; "HB 1"; Back twice | box "HB 1", 19 bills | box "school meals", 89 bills |
| A bill open, the picker to All Terms, Back at once | `/bills?term=all`, "1 matching" | "loading every term…", then 10; each term asked once |
| Scrolled down `/bills?q=housing`, a bill, reload, Back | bare `/bills`, at the top | `/bills?q=housing`, at the place left |

## The not-found page goes to the bill

**What was wrong.** HB 703 of the 2025–2026 term asked for under the term's other year
(`/bill/2026/hb703`), or HB 703 of 2020 under the year it was filed (`/bill/2019/hb703`),
offered only a search, for "HB703" (`n1`).

**What it does now.**
- The page asks for the bill's page at the term's other year, one small request. Meanwhile it
  says "Looking for HB 703 in the 2025–2026 term…".
- Found, it says "HB 703 of the 2025–2026 term is at /bill/2025/hb703" and goes there (`n2`). A
  tab such as `/votes` is kept, and so is the query and the fragment.
- An address with a tab there is no such tab (`/bill/2025/hb703/nosuchtab`) goes to the bill's
  page.
- A number the term does not have keeps the search, written as the record writes it, and the
  search is now of every term: "No page for HB 9999 of 2026. Search for HB 9999 in every term"
  (`n3` before, `n4` after). Before, it searched only the newest term.
- Any address under `/bill/` keeps the lead about bill addresses, `/bill/hb703` most of all.
- **The second review:**
  - The number padded as the General Court writes it (`/bill/2025/hb0703`, or its own
    `HB0703.html` with this host) goes to the bill. So does a real tab with a slash at its end
    (`/bill/2025/hb703/votes/`), and `/BILL/2025/hb703`. Before, each said "No page" for a bill
    that is there, or nothing.
  - A request that fails says "Could not look for HB 703 just now", not that there is no page.
  - `/bill/hb703`, `/bill/2025-2026/hb703` and `/bill/2025/hb-703` offer the search for HB 703.
- It never asks for the address it is on, and goes only to an address that answered, so it
  cannot go round.

## A town not found is told what was meant

**What was wrong.** The lead spoke of bill numbers on every address. `/town/manchster` was told
that "a bill number starts again every two years" (`n5`).

**What it does now.**
- A town's address that is not found says "No town or ward has a page at this address. Did you
  mean Manchester?" (`n6`), from the site search's own list of towns, wards and the 12 cities.
- An address that is a place's name exactly, punctuation aside, goes there:
  `/town/harts-location` is Hart's Location.
- A ward number a city does not have names the city, never another ward, since the wrong ward
  means the wrong representatives: "Did you mean Dover? It has wards 1 to 6." (`n7`, on a
  phone).
- `/town/Dover` and `/town/dover/` are `/town/dover`.
- Any other address that is not a bill's reads "The address may be mistyped." A reader without
  JavaScript gets the page as it was.
- **The second review** (each of these came with the branch's town lookup):
  - A ward address with no number the city has names the city too. `/town/dover-ward` offered
    Dover, Ward 1, and `/town/manchester-ward-1-2` went to Ward 12.
  - The record writes some places short: Chandler's Pur., Crawford's Pur., Wentworth's Loc.,
    Second College Gt, Atk. & Gil. Academy Grant, Thompson & Mes's Purchase. A name is now
    read both as written and with its long words short, so `/town/chandlers-purchase` goes to
    Chandler's Pur. Before, it offered Hadley's Purchase.
  - Two letters swapped count as one slip. Of the 8,728 one-letter slips of the 332 town and
    ward names (a letter dropped, doubled or swapped), 64 are now offered another place, against
    241 with the first fix. A ward's slip that names its city is not counted.
  - The page says "Looking for a town or ward at this address…" while the list arrives.
  - A name whose page is the address the page is on is offered, never gone to, so it cannot
    reload itself.

The walk on dc501057 with the branch's 404 section: every address above went or offered as
written here, with no sideways scroll.

## The shots

`n1`–`n7` are dry run 181's preview, taken on 7 November 2026 at 1280 pixels wide (`n7` at 390).
For the after shots, the preview's own 404 page was served with this branch's not-found section
in place of its own; everything else is the preview's. First, dev's section was put through the
build's link rewriting: it reproduced the preview's page byte for byte, so the after shots
differ by this change alone. The second review changed what the page says only on the roads
above; those walks were on dry run 183, whose 404 section is the release's byte for byte.

## The checks

- `_same_number_one_bill`'s harness keeps the history as a browser does: a stack of entries,
  each its address and state, that Back and Forward move along. It now holds a term's index on
  its way when asked to. It covers 24 orders and 91 steps, including:
  - words typed and never run, and a list of no words, Back twice;
  - Back twice across two lists, with the later list's term turned with no bill open;
  - two topics and an order, at load and after Back;
  - the picker turned with the bill open;
  - Back before a picked term's bills arrive: one request, each bill drawn once.

  It holds that Back pushes nothing, and keeps the whole address, the box and the term.
- `_bill_page_start_and_exit` holds that a reloaded bill page loads the address Back put back,
  and tells the list it is Back.
- `_not_found_finds_the_bill` (new) runs the page's own script in node over 36 addresses. Its
  pages (each bill's real tabs with them) and site-search rows are shaped as the site serves
  them.
- 30 mutants, each one part undone alone, are in the session's scratch `mutants_bnf2.py`; each
  turns its check red.

## Not here, for 24 November (each already on live)

- Back after "Load more" lands above the bill that was opened, since the list is drawn again at
  its first 25.
- A bill's own page with a fragment that is not a bill's (`#results`, which its skip link
  writes, then a reload) draws the term's whole list.
- `history.go(-2)` from one list to an older one leaves the box and list on the later one.
- "Back to search results" on a bill an All Terms address opened (`/bills?q=HB+703&term=all#2020/HB703`)
  draws the list in the bill's own term (the words are kept).
- The picker turned on a list, a bill clicked before that term's bills arrive, then Back: the
  list comes back in the old term, and the box, list and address agree on it.

## For the record, not this weekend

The manager asked for these counts; they go to Alice as a wording question after the webinar.
From the preview's published bill files, all 19 terms:
- 253 of the 12,106 bills that became law have a Law step dated before their Governor step. The
  effective date, as written, comes before the signing; HB 703 of 2020 reads "Law Jan 1, 2020"
  after "Governor Feb 10, 2020".
- 1,618 have a Law step with no date (HB 703 of 2001 is one).

Neither changes here.
