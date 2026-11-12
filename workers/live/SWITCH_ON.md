# Switching Live Now on, and off again

The exact steps, in order, to turn on the live vote feed and to make `/live`
public (about 9 December 2026, DESIGN.md 7.4). **Every step is the owner's
word.** An assistant prepares branches and reads files; it never runs
wrangler, writes the bucket, or changes `main`.

Each step says how to undo it. The emergency stop for everything is the
first row of *Turning it all off* at the end.

## Where things stand before step 1

- The Worker `graniterecord-live` runs in **shadow** since 30 October: YouTube
  on, the database off (no `control.json`).
- `/live` is built every night (`build_live.py`, a step of `build_all.py`)
  but is `noindex` and out of the sitemap (10 November 2026) until `LINKED = True`.
  Nothing on the site links to it yet.
- The Functions `/api/live/streams` and `/api/live/votes/<date>` answer 404
  until the site's Pages project binds `LIVE` (root `wrangler.toml`,
  `[[env.production.r2_buckets]]`).

## 1. Prove the Pages binding (dry run)

| | |
|---|---|
| Do | Run the nightly by hand on `dev` (a dry run, deployed to `dry-run.graniterecord.pages.dev`). Ask the preview for `/api/live/streams`. |
| Pass | 200, with an `ETag` and `X-Robots-Tag: noindex`. |
| If 404 | Either no binding or no file for today. Read `streams/<today>.json` with `npx.cmd wrangler r2 object get graniterecord-live/streams/<today>.json --file s.json --remote`. If the file is there, the binding is missing from the Pages project: add `LIVE` → `graniterecord-live` in the project's settings, or widen the nightly's Pages token if the deploy refused it (DESIGN.md 6.4). A 404 is cached 60 seconds. |
| Undo | Nothing to undo: a preview publishes nothing. |
| Whose word | **owner's** |

## 2. The November test (`sql-test`)

| | |
|---|---|
| Do | (No courtesy note is needed: the IT office already approved reading PublicSQL during session days, the owner said on 9 November 2026.) `npx.cmd wrangler r2 object put graniterecord-live/control.json --file workers/live/control/sql-test.json --remote` |
| Then | Read `test/2026-03-11.json` and `test/2026-08-19.json` and run `node tests/live/compare_test.mjs` on each (README, *The November test*). It says go or no-go. |
| Undo | `npx.cmd wrangler r2 object put graniterecord-live/control.json --file workers/live/control/sql-off.json --remote` (back to shadow at the next run, within 2 minutes). Put it back when the test is done, go or not. |
| Whose word | **owner's** |

## 3. The live vote feed on

| | |
|---|---|
| Needs | Step 2 said go. |
| Do | `npx.cmd wrangler r2 object put graniterecord-live/control.json --file workers/live/control/on.json --remote` (1 December, before the rehearsal: REHEARSAL.md). |
| Check | The next Healthchecks ping says `on`. On a sitting day, `votes/<date>.json` appears and `/api/live/votes/<date>` serves it. |
| Undo | `sql-off.json` as in step 2: the database half stops at the next run, the day's votes file says so once, and the page says the votes were turned off. YouTube stays on. |
| Whose word | **owner's** |

## 4. The pages' branches into `main`

| | |
|---|---|
| Do | Merge the live branches that dev holds by then (the morning page, In short, the overlay: `live/session`) into `main` for the next night's publish, after preflight's full suite on `dev`. |
| Check | The night's log has the live session step; `/session/<B>/<date>` is the morning page on a sitting's morning. |
| Undo | Revert the merge on `main`; the next night publishes without it. The retired `/session/<B>/today` stays retired. |
| Whose word | **owner's** (a change to `main`) |

## 5. Make `/live` public

Each of these is its own commit on a live branch, merged to `main` on the
owner's word, and each is undone by reverting it.

| Link | Where | Whose word |
|---|---|---|
| The home page's line, "Live Now — N meetings today", and the header search's row for Live Now | one switch: `LINKED = True` in `src/pages/build_live.py` (with its version stamp). `build_pages` leaves the home page a slot and `build_live` fills it, and puts its own row in `find.json`; while `LINKED` is `False` it takes both out (PATCHES.md 2 and 3) | **owner's** |
| The committee pages' player | `live_hook.place` in the committee builders (PATCHES.md 11) | **owner's** |
| The live votes file's documentation, For Developers | `live_docs.PUBLIC = True` (live/docs) | **owner's** |

Undo: revert the commit. The page itself stays built; `LINKED = False` makes it `noindex` and takes it
out of the sitemap again, and the links go.

## Turning it all off

| What | Command or step | Effect | Whose word |
|---|---|---|---|
| **Everything, now** | `npx.cmd wrangler r2 object put graniterecord-live/control.json --file workers/live/control/all-off.json --remote` | Within 2 minutes: nothing asks YouTube or the database. The streams file says `"problem": "off"`; the pages say live status is not available. State keeps nothing of YouTube. | **owner's** |
| The database half only | `… --file workers/live/control/sql-off.json --remote` | Votes stop; streams go on. | **owner's** |
| The page's data | remove `LIVE` from the Pages project's bindings, then publish | Both Functions answer 404; the pages draw without live data, as they were built to. | **owner's** |
| The Worker | `npx.cmd wrangler delete --config workers/live/wrangler.toml --env production` | No runs at all. Last resort: `all-off.json` does the same without losing the deployment. | **owner's** |
| The links | revert step 5's commits | `/live` is unlinked again. | **owner's** |

Back on after `all-off.json`: put `sql-off.json` (shadow) or `on.json`. After
a refused YouTube key: `all-off.json`, one run (2 minutes), then the new key
and `sql-off.json` (README, *The switch*).
