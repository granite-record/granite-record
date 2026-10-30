# workers/live/

The live Worker, `graniterecord-live`: Live Now's data. Every 2 minutes its
cron asks YouTube's Data API which House and Senate streams are live,
scheduled for today, or ended today, and writes the answer to a private R2
bucket, `graniterecord-live`. A read-only Pages Function serves that file to
the Live Now page (both come in later branches); no page waits on it, and
the page says when live status was last checked, never "nothing is live".

It has no address, answers no request, and asks nobody but YouTube and
Healthchecks. It never asks gc.nh.gov or the General Court's database (its
database half is a later branch, and `control.json` keeps it off until the
person turns it on), never reads the site, and keeps nothing a reader
gave it.

| File | What it is |
|---|---|
| `index.js` | the run: reads the switch and the state, works out what is due, takes the lease, looks, writes, releases, pings |
| `clock.js` | New Hampshire's clock and the cadence (below) |
| `youtube.js` | the calls, how a video's status is read, and today's file |
| `store.js` | the bucket: the switch, the state, the lease, the 30-day sweep |
| `live.gen.js` | written by `python3 src/pages/live_gen.py`: the channels, the night's windows, the session-title pattern. Never edit it by hand |
| `control/` | the person's four ready-made switches |
| `wrangler.toml` | the local Worker at the top level; production under `[env.production]` |

## What it asks, and when

On New Hampshire's clock, from what the last run did (`clock.js`):

- **Weekdays 07:00 to 20:00** (every stream start on record, 2020 to 2026,
  fell inside): every run reads both channels' uploads playlists, newest 50,
  and asks `videos.list` after what is new, live, or due to start from two
  hours ago to the end of today. The first run of the day re-asks every
  upcoming stream it keeps, so one scheduled weeks ahead and pushed out of the
  newest 50 is still found on its day. Every 30 minutes, `search.list` asks
  each channel what is live: the backstop for a stream nobody scheduled, which
  the playlist may not carry until it ends.
- **Outside those hours and at weekends:** the playlists every 30 minutes,
  and every 10 minutes the streams still live, so a session that runs to
  midnight is followed to its end.

At most 1,300 of the Google project's 10,000 units on a weekday (the night's
`livestreams.py` uses the same project), and 52 of search's own 100 calls:
`tests/live/youtube.test.js` holds both over a simulated heavy week, and
preflight prints the busiest day it counted. Quota resets at midnight
Pacific.

## What it writes

| Object | Written by | Kept |
|---|---|---|
| `control.json` | **the person only** (below) | until replaced |
| `state.json` | the Worker: the lease, the day's counts, what the next run needs | overwritten |
| `streams/<date>.json` | the Worker: that New Hampshire day's streams | 30 days |
| `lease-waits.json` | the Worker, only when a run finds another run's lease | overwritten |

`streams/<date>.json`:

```json
{"kind": "live.streams", "day": "2027-01-07",
 "checked": "2027-01-07T15:02:04Z", "next_check": "2027-01-07T15:04:04Z",
 "status": {"ok": true, "problem": null, "since": null},
 "streams": [
   {"video": "AbCdEfGhIjK", "chamber": "H", "title": "House Finance (01/07/2027)",
    "status": "live", "scheduled": "2027-01-07T15:00:00Z", "started": "2027-01-07T15:01:37Z",
    "ended": null, "embeddable": true,
    "seen": {"playlist": "2027-01-07T15:02:04Z", "search": null}}]}
```

- `checked` is the last look that worked; `next_check` is when the Worker will
  next look. A page that finds now more than 5 minutes past `next_check` says
  live status has not been checked since `checked`.
- `status.ok` false means the streams are as of `checked` and are not
  current. `status.problem` says why, from `since`: `youtube` (a look failed;
  tried again at the next), `quota` (YouTube's quota is spent; held to
  midnight Pacific), `key` (no key, or YouTube refused it; a refused key is
  held for the rest of the day) or `off` (`control.json`).
- `status` of a stream is `live`, `upcoming` (scheduled for today) or
  `ended` (today, for "Earlier today"). A stream YouTube leaves out of an
  answer is kept as last seen for three looks in a row, then dropped.
- `seen` is when each path, the playlist or search, first listed the stream
  that day: the measurement of whether the playlist carries a stream nobody
  scheduled while it is live.

The Worker deletes every `streams/`, `votes/` and `test/` object last written
30 calendar days ago, on its first run after 03:00: YouTube's developer
policy keeps its data "not longer than 30 calendar days" (III.E.4.d).
`state.json` keeps of YouTube only what the next look needs (upcoming ids,
ids live, the last playlist reads), none of it past 30 days unrefreshed, and
nothing at all once YouTube is switched off.

## Setting it up (the person, once)

From the repository folder, in PowerShell (`npx.cmd` there; `npx` elsewhere).

1. **The bucket**, private: no custom domain and no `r2.dev` address.

   ```
   npx wrangler r2 bucket create graniterecord-live
   ```

2. **The YouTube key.** A second key in the Google Cloud project the night's
   key is in (YouTube's developer policy III.D asks for one project per
   application): APIs & Services → Credentials → Create credentials → API key.
   Under API restrictions, restrict it to **YouTube Data API v3**. Leave
   application restrictions off: a Worker has no fixed address. Then give it
   to the Worker, and paste it when asked:

   ```
   npx wrangler secret put YOUTUBE_API_KEY --config workers/live/wrangler.toml --env production
   ```

   If wrangler asks whether to create the Worker `graniterecord-live` to hold
   the secret, say yes; the deploy below fills it in.

3. **The Healthchecks check.** On healthchecks.io, a new check named
   `graniterecord-live`, period 2 minutes, grace 10 minutes. Copy its ping
   URL and give it to the Worker:

   ```
   npx wrangler secret put HEALTHCHECK_URL --config workers/live/wrangler.toml --env production
   ```

4. **Deploy it.**

   ```
   npx wrangler deploy --config workers/live/wrangler.toml --env production
   ```

Its first run is within 2 minutes. With no `control.json` it runs in
**shadow**: YouTube on, the database off. Healthchecks receives every run's
codes, and what `control.json` says.

The secrets are stored by Cloudflare, encrypted, and never in this
repository. Without `--env production` a command reaches the local Worker's
name, `graniterecord-live-local`, which is never deployed; preflight fails if
a command here lacks it.

## The switch: control.json

The person writes `control.json`; the Worker only reads it, at the start of
every run, and says in every Healthchecks ping what it is honouring.
Missing or unreadable means shadow. Four ready-made files:

| File | YouTube | Database |
|---|---|---|
| `control/sql-off.json` | on | off (shadow, the same as no file) |
| `control/sql-test.json` | on | the November test (below) |
| `control/on.json` | on | on: the session reads (below) |
| `control/all-off.json` | off | off |

```
npx wrangler r2 object put graniterecord-live/control.json --file workers/live/control/sql-off.json --remote
npx wrangler r2 object put graniterecord-live/control.json --file workers/live/control/sql-test.json --remote
npx wrangler r2 object put graniterecord-live/control.json --file workers/live/control/on.json --remote
npx wrangler r2 object put graniterecord-live/control.json --file workers/live/control/all-off.json --remote
```

**`--remote` every time:** without it, wrangler's `r2 object` commands write
a local copy on this machine and the Worker never sees it. preflight fails if
a line here lacks it. A switch takes effect at the next run, within 2
minutes. With YouTube off, the day's file says `"problem": "off"` once,
nothing is asked, and `state.json` forgets what it kept of YouTube, holds
included. So after putting a new key in place of one YouTube refused, put
`all-off.json`, wait one run (2 minutes), and put `sql-off.json`: the new key
is tried at once rather than the next day.

A `control.json` the Worker cannot read (bad JSON, or a value not in the
table, such as `"of"`) is honoured as shadow, and every run sends `/fail`
until it is replaced.

To read what it wrote, for example a day's streams and their `seen` times:

```
npx wrangler r2 object get graniterecord-live/streams/2026-11-16.json --file streams-2026-11-16.json --remote
```

## The November test (`sql-test`)

The one gate before any sitting (DESIGN.md 2.7), on the person's word and
after the courtesy note to the General Court's IT office. With `sql-test.json`
in place, the first run between 10:00 and 16:00 on each weekday makes one
connection to the General Court's public SQL database, and nothing else in
the Worker reads it:

- the first weekday reads 11 March 2026 and writes `test/2026-03-11.json`;
- the next, 19 August 2026 (veto day), `test/2026-08-19.json`;
- every weekday after, a login alone: `test/login/<date>.json`.

Each past sitting is read once. A day the server refused (no connection, the
login refused, encryption required) sends `/fail` and asks the same sitting
on the next weekday; a statement that failed is the file's to say, and the
sitting is not asked again. Read the files and compare them on the laptop:

```
npx wrangler r2 object get graniterecord-live/test/2026-03-11.json --file test-2026-03-11.json --remote
node tests/live/compare_test.mjs test-2026-03-11.json
npx wrangler r2 object get graniterecord-live/test/2026-08-19.json --file test-2026-08-19.json --remote
node tests/live/compare_test.mjs test-2026-08-19.json
```

`compare_test.mjs` says go or no-go, and why. Put `sql-off.json` back when
the test is done. Before Q3's comparison, measure the docket's own habits
from the kit (DESIGN.md 7.3; no network):

```
node tests/live/measure_docket.mjs <the kit's Docket.txt> 2025 2026
```

Under 95% on either line, Q3's text test is widened before it is relied on.

## The session reads (`on`)

With `on.json` in place, each run works out each chamber's state
(DESIGN.md 2.3) and reads the General Court's database only as that state
calls for, one connection a run for both chambers, closed at once:

| State | When | Reads |
|---|---|---|
| hot | its session stream is live or about to start, or a roll call dated today was first seen in the last 45 minutes | every run: Q1 (today; the last 14 days every 10 minutes), Q3, Q2 for up to 20 roll calls |
| warm | for 5 hours after it was last hot, never past 23:59 | every 10 minutes: Q1 over 14 days, Q3, Q2 |
| heartbeat | weekdays, 08:30 EST / 09:30 EDT to 18:00, January to June, and in the 14 days after a day it was hot | every 15 minutes: Q1 over 14 days alone |
| off | otherwise | nothing |

The night's windows (`refusal.NIGHT_WINDOWS`) start no warm or heartbeat
read; a hot one goes ahead there only for a chamber whose session stream is
live. At 600 connections, 1,200 statements or 150,000 rows in a New
Hampshire day it holds until the next day.

It writes `votes/<date>.json`, filed under each roll call's own date, the
public live votes file (DESIGN.md 5): a roll call once shown is never
dropped; one the database stops listing gains a note. Each docket tally
carries, beside section 5's fields, `bill_as_recorded`, `abbrev` (the key's
abbreviation), `order` (the docket's statusorder) and `entered` (when the
clerk entered the line, UTC). A tally is attached to its roll call only when
that is certain: as many lines as roll calls with the same bill and tally. Holds end by the next
day at the latest and none needs a person; each sends `/fail` while it
stands. To read a day's file:

```
npx wrangler r2 object get graniterecord-live/votes/2027-01-07.json --file votes-2027-01-07.json --remote
```

Turning the database half off (`sql-off.json`) is honoured at the next run,
and the day's file says so once.

## The two Functions that serve it (functions/api/live/)

Read-only Pages Functions on the site's own project, deployed with every
Pages publish (DESIGN.md 5 and 6.4):

| Address | Serves | Headers |
|---|---|---|
| `/api/live/votes/<YYYY-MM-DD>` | `votes/<date>.json`: public, provisional, API v1 beta | CORS open; `max-age=15`; ETag and 304; 404 (60 s) for a date with no file |
| `/api/live/streams` | today's `streams/<date>.json` (yesterday's in the hour after midnight): Live Now's own data, not public API | no CORS; `X-Robots-Tag: noindex`; `max-age=30`; ETag and 304 |

Both answer 404 everywhere until the site's `wrangler.toml` binds `LIVE`
(after the bucket exists), GET and HEAD only, 503 when the bucket cannot be
read, and keep a copy per data centre through the Cache API.
`functions/api/live/_store.js` is the one file that names `env.LIVE`, and it
hands back `get` and `head` alone; preflight fails if any file there writes,
deletes, lists or uploads. No other object in the bucket is reachable.

## The pages that read it, and the night's copy

Nothing here writes the site, and the night never writes the bucket
(DESIGN.md 4.4). The pages fetch the two Functions' answers; the night
writes everything else.

| What | Written by | Reads |
|---|---|---|
| `/live` and `live/schedule.json` | `src/pages/build_live.py` (night) | `/api/live/streams`, every minute; on a sitting day, `/api/live/votes/<day>` |
| `/session/H/today`, `/session/S/today` | `src/pages/build_live_session.py` (night) | the reader's day (the day before until 06:00): its record file, the votes file and the streams |
| a dated session-day page's overlay (`#live-votes`) | `build_session_pages.py`, PATCHES.md 6 | within 14 days: its record file, then the votes file, polled only on the day itself |
| `/session/<H\|S>/<date>.json` | `build_live_session.py` (night) | nothing; this is the record's copy of the day, in the live file's shape |
| `/schema/session.votes.json` | copied from `schema/` by the same step | the one shape for both |

**The record wins by id.** A page draws the record's roll calls, and adds
from the live file only the ids the record lacks, marked provisional. Once
the night's record holds a roll call, its live copy is not drawn again.
Nobody has to supersede anything by hand.

`src/pages/live.js` is the browser's half of all of it. Tests:
`tests/live/page.test.js`. The shape's tests are `tests/live/schema.test.js`
and preflight's `_live_session`, which run the same cases through the node
checker and the Python one.

**The documentation waits for the person.** `src/pages/live_docs.py` holds
the data page's "Same Day, Provisional" section and the manifest's `live`
entry. Neither is published until `live_docs.PUBLIC` is True, which the
person sets in the change that links Live Now. preflight's `_live_docs` holds
the numbers in that text (15 s, 60 s, 30 days) to the Function and the Worker.

## When Healthchecks says it failed

The ping body says why. `/fail` is sent when:

- YouTube's quota is spent: the YouTube half waits for midnight Pacific;
- search's own allowance is spent: search waits for midnight Pacific, and the
  playlists are still read;
- three ticks in a row found another run's lease: the cron firing twice, or
  a second Worker on this bucket;
- a run had something due and wrote nothing;
- the November test could not read (the server refused), or its file could
  not be written;
- a session read could not be made, or a votes file not written.

And on every run, until it is mended, so the check stays down rather than
flapping:

- there is no `YOUTUBE_API_KEY` (step 2);
- YouTube refused the key: held to New Hampshire's midnight, or until
  YouTube is turned off and on with a new key;
- five or more looks in a row have failed;
- `control.json` cannot be read;
- a votes hold (connect, login, encrypt, query, budget) stands.

## The guard's two entries (the person's to apply)

`guard.patch` is a proposed change to `.claude/hooks/guard.py`, which only the
person changes: `git apply workers/live/guard.patch`. It **denies** `wrangler dev`
aimed at this Worker (`--config`/`-c workers/live/...`, or run from inside
`workers/live/`) with `--env`/`-e production` or `--remote`, which would run it
against the General Court's database from a laptop; it **asks**, with its own
reason, before a put of `graniterecord-live/control.json`. It also makes the
guard see `npx.cmd wrangler`, PowerShell's form, which today's guard misses.

## Trying it on this machine

```
npx wrangler dev --config workers/live/wrangler.toml --test-scheduled
```

and then `http://localhost:8787/__scheduled` runs one cron. The top level
binds a local bucket, has no cron and no secrets, and is never deployed: with
no key, the run writes `"problem": "key"` and asks YouTube nothing.

## Checked by

`node --test tests/live/index.js`, which preflight runs (`_live_tests`):
the cadence across both changes of the clock in 2027; live, upcoming, ended,
unscheduled and cancelled streams, against a YouTube that is a function
answering synthetic answers in the documented shape; a heavy week's quota;
every failure said; the lease; the sweep; and the switch. preflight's
`_live_layer` holds the rest: `live.gen.js` current, the cron and bucket
production's alone, no route, the commands above, the four switches, and the
Worker's reading of a title and a status equal to the night's Python.
