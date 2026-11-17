# workers/bench/

The shared bench: people the owner invites check the site's work one item at
a time from a private link -- whether a hearing starts and ends where the
site says, whether a bill's topic or tag is fair -- and their answers reach
`review/checked.jsonl` only through the owner's merge. Approved by the owner
on 17 November 2026 (the design's decisions 1 to 14 as recommended; 15: no
rate rule on the zone at first, the Functions' own limits only).

No Worker of its own: this folder holds the database's schema and the code
the Pages Functions share, outside `functions/` so that none of it can become
a route, as `workers/follow/`'s does.

- `schema.sql` -- the tables, and what each column keeps.
- `store.js` -- every database call: a link found by its token's hash, an
  item claimed in one statement and held, an answer kept with its item marked
  judged in one batch, undo, the daily cap, calibration, how far along, and
  the owner's Links page.
- `common.js` -- the switch, the address and origin rules, reading a body,
  answering (the page's own rules for scripts and frames among them) and the
  log, which is a code and a count and nothing else.
- `view.js` -- what the page is told after each call: an item as `{ ref,
  queue, card }`, never its key (which says, of a tag, how the rule attached
  it) or whether it is a calibration item.
- `page.js` -- the page itself, which `functions/bench.js` answers.

## The routes

Every one answers 404 until `BENCH_DB` is bound in `wrangler.toml` for the
environment, and only at its own address on the site's own names:

| route | what |
|---|---|
| `GET /bench` | the page (`functions/bench.js`) |
| `POST /api/bench/next` | what this link holds, two at most, and how far along |
| `POST /api/bench/judge` | an answer, kept; the next items |
| `POST /api/bench/undo` | the latest answer back, while not merged |
| `POST /api/bench/hold` | the open page's items held ten more minutes |
| `POST /api/bench/links` | the owner's Links tab: list, make, pause, resume, take back, turn off |

Each post is JSON of at most 4 KiB from the site's own page (its Origin,
and Sec-Fetch-Site where the browser sends it), carrying the token from
after "#" in the link. A wrong token, or a link turned off, is one indexed
read and the same 404 as no bench at all.

## What it keeps

Of a person: the name the owner gives the link, the day it was made and the
day it was last used. No email, IP address, cookie, device or referrer; the
token itself is never kept, only its SHA-256. An answer is kept with the
link's id, and goes into the public ledger under that id, never the name,
once the owner approves it on the laptop (`src/checks/bench_pull.py`).

## The limits

Each a guess of the design's, written once in `store.js`: an item held ten
minutes, renewed every two while the page is open (`HOLD_MS`); two held at
once (`HELD_MOST`); 500 answers a day for a contributor's link
(`DAILY_CAP`, counted and raised in one statement); one answer a second
(`GAP_MS`); notes of 280 characters (`NOTE_MOST`); one item in 25 a
contributor is given is one the owner judged already (`CALIB_EVERY`), never
one that link has answered, and its answer is never merged.

## The database

Two, made by the owner, never by an assistant or the night:

    npx wrangler d1 create graniterecord-bench-preview
    npx wrangler d1 create graniterecord-bench
    npx wrangler d1 execute graniterecord-bench-preview --remote --file workers/bench/schema.sql
    npx wrangler d1 execute graniterecord-bench --remote --file workers/bench/schema.sql

Applying the schema again changes nothing (IF NOT EXISTS throughout).

Run by: nothing on its own. Tested by `tests/bench/` (`node --test
tests/bench/index.js`), on the follow tests' fake D1 with this schema;
preflight's `_bench_tests` runs them.
