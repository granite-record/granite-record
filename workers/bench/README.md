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
| `POST /api/bench/asks` | the owner's Your input tab: her list, and her answer to one entry |

Each post is JSON of at most 4 KiB (8 KiB to `/api/bench/asks`, for a note
of 2,000 characters) from the site's own page (its Origin, and
Sec-Fetch-Site where the browser sends it), carrying the token from after
"#" in the link. A wrong token, or a link turned off, is one indexed read
and the same 404 as no bench at all.

## What it keeps

Of a person: the name the owner gives the link, the day it was made and the
day it was last used. No email, IP address, cookie, device or referrer; the
token itself is never kept, only its SHA-256. An answer is kept with the
link's id, and goes into the public ledger under that id, never the name,
once the owner approves it on the laptop (`src/checks/bench_pull.py`).

On the device, the page keeps the token in the browser's own storage
(`localStorage`, under `gr.bench`), so `/bench` alone opens the bench again
there, until the link is turned off (the bench then answers 404 and the page
forgets it) or "Forget this link on this device" is pressed. A token in the
address always replaces the kept one. Nothing new is kept on the server.

## The limits

Each a guess of the design's, written once in `store.js`: an item held ten
minutes, renewed every two while the page is open (`HOLD_MS`); two held at
once (`HELD_MOST`); 500 answers a day for a contributor's link
(`DAILY_CAP`, counted and raised in one statement); one answer a second
(`GAP_MS`); notes of 280 characters (`NOTE_MOST`); one item in 25 a
contributor is given is one the owner judged already (`CALIB_EVERY`), never
one that link has answered, and its answer is never merged.

## What is asked: a pack

`python3 src/checks/bench_pack.py --preview` (or without `--preview` for
production's) draws what contributors are asked next from `review.py`'s own
pools -- hearing timings a year a group, placed topics a term a group, a
tag's single-bill samples a tag a group -- leaving out every key the ledger
holds and every key an earlier pack for that database holds, with the
owner's own judgments for calibration. It writes
`reports/bench/packs/<preview|production>/<date>.sql` and prints the one
wrangler command that loads it; the owner runs that.

A later pack is served after every earlier one: its items and groups are
numbered from a million times the packs already in that folder (`ord`), and
calibration keeps its own order. `--queues tag,topic` draws only those
queues, `--groups-of tag=all` (or a number) sets one queue's groups in place
of `--groups`, and `--pools DIR` and `--ledger FILE` read the pools and a
copy of the ledger from elsewhere, so a pack can be drawn in a scratch tree
with nothing written in `review/`.

## What was answered: the merge

`python3 src/checks/bench_pull.py` (the owner's, on the laptop) pulls every
answer not merged yet, screens every note with `compile_reports.screen`
(a contributor's note is untrusted, like a reader's report; one it holds is
not printed or merged, and `--show ID` prints its words for her), and
prints each link's answers, its agreement with hers on calibration items,
and any clash with an answer of hers. `--approve <name or id>` appends that
link's answers to `review/checked.jsonl` through `review.record`, as
`"by": "link:<id>"` (hers as `"hand"`), each once, and marks them merged;
only production's. `--withdraw <id>` is one appended line every reader
honours. `--owner-link` makes her own link, shown once.

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
