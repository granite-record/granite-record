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
   {"video": "AbCdEfGhIjK", "chamber": "H", "title": "House Finance (01/07/2027)", "session": null,
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
  held for the day, or until a new one is put) or `off` (`control.json`).
- `status` of a stream is `live`, `upcoming` (scheduled for today) or
  `ended` (today, for "Earlier today"). `session` is `H` or `S` for a
  chamber's session stream.
- `seen` is when each path, the playlist or search, first listed the stream
  that day: the measurement of whether the playlist carries a stream nobody
  scheduled while it is live.

The Worker deletes every `streams/`, `votes/` and `test/` object last written
30 calendar days ago, on its first run after 03:00: YouTube's developer
policy keeps its data "not longer than 30 calendar days" (III.E.4.d).

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
| `control/sql-test.json` | on | the November test (a later branch) |
| `control/on.json` | on | on (a later branch) |
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
minutes. With YouTube off, the day's file says `"problem": "off"` once and
nothing is asked.

To read what it wrote, for example a day's streams and their `seen` times:

```
npx wrangler r2 object get graniterecord-live/streams/2026-11-16.json --file streams-2026-11-16.json --remote
```

## When Healthchecks says it failed

The ping body says why. `/fail` is sent when:

- YouTube's quota is spent, or it refused the key: the YouTube half waits for
  midnight Pacific, or for New Hampshire's midnight or a new key;
- there is no `YOUTUBE_API_KEY` (step 2);
- five looks in a row have failed;
- three ticks in a row found another run's lease: the cron firing twice, or
  a second Worker on this bucket;
- a run had something due and wrote nothing.

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
