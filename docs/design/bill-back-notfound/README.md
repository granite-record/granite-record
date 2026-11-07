# Back keeps the search; the not-found page finds the bill (for the weekend release)

The branch is `fix/bill-back-notfound`, on top of `release/weekend` (with dev 969c27fa merged
in), for the second dry run. The laptop manager's browser test of 7 November 2026, on dry run
181's preview, found these. Three reviews of the fix, and the deep walk of dry run 183, found
more on the same roads. All of them are on live too, except where a line says the branch
made it.

## Back from a bill keeps the search

**What was wrong.** On `/bills`, with All Terms chosen, search HB 703, open a result, then press
Back. The list showed the search's results, but the address had lost its words:
`bills?q=HB+703&term=all` became `bills?term=all`. A reload or a shared link lost the search,
and Forward no longer reached the bill. Back had put the list's own address back, and the page
then pushed a bare `/bills` over it.

**What it does now.**
- On Back the page pushes nothing, and Forward reopens the bill, on the tab its address names.
- The list is drawn as its own history entry names it: its words, its term, every filter ticked
  and its order. The box, the list and the address agree.
- A list's address names its words only where a search was run. Words typed and not run are in
  no address, so the list's entry keeps them beside its address, at every drawing of the list.
  Back to it, after Forward or after a reload, draws what the reader left.
- A term or an order chosen with the bill open is the reader's for the list behind it, and
  Back draws the list in it.
- **Back twice**: from a later list of another search and term, past the bill, to the first
  list, draws the first list as it was.
- **Reload a bill, then Back**: the page loads the address Back put back, with its words, and
  opens it where the reader stood in the list. It used to send the reader to bare `/bills`,
  the newest term with an empty box: the likeliest road to the empty box the manager saw.
- **Back before a term's bills arrive** (the picker turned with the bill open, then Back at
  once): each term is asked for once at a time, and the list says "loading…" and nothing else
  until its bills are here. A term whose bills fail to come is drawn as far as it came, and
  asked for again the next time.
- **"Back to search results"** on a bill that an address opened over the search
  (`/bills?q=…#2020/HB703`) keeps the search's words.
- A search that finds nothing offers only what is left to try: no "Try removing a filter, or a
  different term" with no filter ticked and All Terms chosen.

**Made by the branch, and fixed before it went out** (found by the reviews and the walk):
- Back kept only the first of two ticked topics. Every topic the address names is read now, on
  Back and when the page loads; on live a page loaded at a two-topic address lost the second.
- The picker, then Back at once, drew every bill of that term twice.
- The words kept in a list's entry went stale when the box changed after Back.
- An order chosen with the bill open was dropped on Back.
- Forward to a bill whose tab was chosen drew its Summary under the tab's address.

A browser walk on dry run 183's own deployment (dc501057), the branch's app.js served in place
of its own:

| Road | Dry run 183 (and live) | This branch |
|---|---|---|
| Search HB 703 in All Terms, open 2020's, a new search typed, Back twice | `/bills?term=all`, the later search's list | `/bills?q=HB+703&term=all`, box "HB 703", 10 bills |
| Then Forward | the bill is gone | `/bill/2020/hb703` |
| Two topics, open a bill, Back | one topic at load, 250 bills | both topics, 289 bills, Back and Forward alike |
| `/bills?status=Passed`, a bill, "dog", Back twice | box "dog", 10 bills | box empty, 686 bills |
| "school meals" typed, not run; a bill; "HB 1"; Back twice | box "HB 1", 19 bills | box "school meals", 89 bills |
| Back, then "dog" typed, Forward, Back | (Forward goes nowhere) | box "dog", 294 bills |
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
- The number padded as the General Court writes it (`/bill/2025/hb0703`), a real tab with a
  slash at its end (`/bill/2025/hb703/votes/`), and `/BILL/2025/hb703` go to the bill. So does
  the General Court's own address of a bill with this site's host,
  `/legislation/2025/HB0703.html`.
- A number the term does not have keeps the search, written as the record writes it, and the
  search is now of every term: "No page for HB 9999 of 2026. Search for HB 9999 in every term"
  (`n3` before, `n4` after). Before, it searched only the newest term.
- A request that fails says "Could not look for HB 703 just now", not that there is no page.
- Any address under `/bill/` keeps the lead about bill addresses. `/bill/hb703`,
  `/bill/2025-2026/hb703` and `/bill/2025/hb-703` offer the search for HB 703.
- It never asks for the address it is on (with or without `.html`), and goes only to an
  address that answered, so it cannot go round.

## A town not found is told what was meant

**What was wrong.** The lead spoke of bill numbers on every address. `/town/manchster` was told
that "a bill number starts again every two years" (`n5`).

**What it does now.**
- A town's address that is not found says "No town or ward has a page at this address. Did you
  mean Manchester?" (`n6`), from the site search's own list of towns, wards and the 12 cities.
  It says "Looking for a town or ward at this address…" while the list arrives.
- An address that is a place's name exactly, punctuation aside, goes there:
  `/town/harts-location` is Hart's Location, with or without `.html`.
- The record writes some places short: Chandler's Pur., Crawford's Pur., Wentworth's Loc.,
  Second College Gt, Atk. & Gil. Academy Grant, Thompson & Mes's Purchase. A name of more than
  one word is read both as written and with its long words short, so
  `/town/chandlers-purchase` goes to Chandler's Pur. A one-word name (Atkinson, Gilmanton) is
  never made short.
- A ward number a city does not have names the city, never another ward, since the wrong ward
  means the wrong representatives: "Did you mean Dover? It has wards 1 to 6." (`n7`, on a
  phone). So does a ward with no number (`/town/dover-ward`, `/town/manchester-ward-1-2`), and
  a slip that lands near a ward (`/town/manchester-war-11`, one letter from Ward 1 and from
  Ward 11).
- Where an address names a ward, the place meant is a city that has wards before a town of the
  same distance with none: `/town/ochester-ward-3` is Rochester, Ward 3, not Chester.
- Two letters swapped count as one slip, and a name of four letters or fewer allows one slip:
  `/town/xyz` is not offered Rye.
- A name whose page is the address the page is on is offered, never gone to, so it cannot
  reload itself.
- `/town/Dover` and `/town/dover/` are `/town/dover`.
- Any other address that is not a bill's reads "The address may be mistyped." A reader without
  JavaScript gets the page as it was.

Of the 8,728 one-letter slips of the 332 town and ward names in dry run 183's site search (a
letter dropped, doubled or swapped), 40 are offered or sent to another place, against 241 with
the first fix. Most of the 40 are themselves another place's name (Eaton for Easton, Ward 1 for
Ward 10). A ward's slip that names its own city is not counted.

The walk on dc501057 with the branch's 404 section: every address above went or offered as
written here, with no sideways scroll.

## The shots

`n1`–`n7` are dry run 181's preview, taken on 7 November 2026 at 1280 pixels wide (`n7` at 390).
For the after shots, the preview's own 404 page was served with this branch's not-found section
in place of its own; everything else is the preview's. First, dev's section was put through the
build's link rewriting: it reproduced the preview's page byte for byte, so the after shots
differ by this change alone. The reviews changed what the page says only on the roads above;
those walks were on dry run 183, whose 404 section is the release's byte for byte.

## The checks

- `_same_number_one_bill`'s harness keeps the history as a browser does: a stack of entries,
  each its address and state, that Back and Forward move along. It can hold or refuse a term's
  index, tick a facet and choose an order. It covers 30 orders and 124 steps, including:
  - words typed and never run, a list of no words, and the box changed after Back, each with
    Back twice or Forward and Back;
  - Back twice across two lists, with the later list's term, order or filter changed;
  - two topics and an order, at load and after Back;
  - the picker, or the order, turned with the bill open;
  - Back before a picked term's bills arrive: "loading", one request, each bill drawn once;
  - a term refused, then asked for again;
  - a page loaded at a list's entry that holds words;
  - a search that finds nothing, in All Terms, in one term, and with a topic ticked.

  It holds that Back pushes nothing, and keeps the whole address, the box and the term.
- `_bill_page_start_and_exit` holds that a reloaded bill page loads the address Back put back,
  and tells the list it is Back, and that "Back to search results" over a search keeps its
  words.
- `_not_found_finds_the_bill` (new) runs the page's own script in node over 45 addresses. Its
  pages (each bill's real tabs with them) and site-search rows are shaped as the site serves
  them.
- 49 mutants, each one part undone alone, are in the session's scratch `mutants_bnf2.py`. 48
  turn their check red. The one that does not undoes the words a list saves when a bill is
  opened from it. The list saves them at every drawing too, so that save matters only for a
  bill clicked in the 400 ms before typed words are drawn, which the node harness cannot hold
  open. It is kept as a guard.
- Forward to a bill on its tab was walked in the browser, since the harness does not draw tabs.

## Not here, for 24 November (each already on live)

- Back after "Load more" lands above the bill that was opened, since the list is drawn again at
  its first 25.
- A bill's own page with a fragment that is not a bill's (`#results`, which its skip link
  writes, then a reload) draws the term's whole list.
- `history.go(-2)` from one list to an older one leaves the box and list on the later one.
- "Back to search results" on a bill an All Terms address opened (`/bills?q=HB+703&term=all#2020/HB703`)
  draws the list in the bill's own term (the words are kept); Back from there leaves the list
  under the bill's address.
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
