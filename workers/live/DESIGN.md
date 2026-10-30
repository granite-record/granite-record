# The live layer: final design

> **§1.6 added 30 October 2026**, as the owner approved it on 29 October (a committee page's live stream; with it, the streams answer's cache moves from 15 to 30 seconds, §5).
>
> **As committed (29 October 2026).** This is the approved design, unchanged except that the General Court's SQL host is written as `probe_db.HOST` rather than its address, so that the live checks' rule (the host appears only on production's line of `workers/live/wrangler.toml`) holds for this file too. Paths under `/tmp/claude-0/` name the original session's scratch files and experiments; they were not kept. The working notes it cites (`plan.md`, `streams.md`, `votes.md`, `api.md`) were the session's, not the repository's.

Live Now, session-day votes as they come in, the store between them and the pages, and the public API's live file.

26 October 2026. This is the design to build from. It merges designs A and B (`/tmp/claude-0/audit/wf16/design_A.md`, `design_B.md`) and answers all three reviews ("works", "safe" and "simple"). Two of the three reviews preferred B, so **B is the base**. A supplies the reading rules (no clock cap, the Senate's docket lines found by the date in their text, re-reading a day whole), the YouTube discovery fixes, the build order and the per-cause messages. Every high and medium problem the reviews raised is answered; §11 says where.

**What I read:**
- `plan.md` §2, 3, 4 and 8; `streams.md`, `votes.md` and `api.md` in full.
- Designs A and B in full, and the three reviews with their notes.
- The repository at `origin/dev` `0c45848`, extracted with `git archive` to `/tmp/claude-0/audit/wf16/final/tree`. The checkout was not touched.
- In that tree, checked for this design:
  - the root `wrangler.toml` (previews get their own stores);
  - `workers/night-timer/` (`scheduled()` ignores `event.cron`);
  - `workers/follow/wrangler.toml`, `common.js` (`nhClock` is exported) and `site.gen.js` (the generated-module pattern);
  - `nightly.yml`: "NO SECRET: the credentials are the published ones in probe_db.py". A dispatch's defaults are `dry_run: true` and `fetch: false`. Preflight `--code` runs before anything is fetched or deployed;
  - `probe_db.py` (`HOST`, the published login, the expiring hold, the 4060 exception);
  - `refusal.py` (`NIGHT_WINDOWS`; `window_check` covers the SQL host on a stood-down laptop);
  - `build_session_pages.sittings` ("A SITTING CANNOT BE AFTER THE BUILD"), `prune` (it removes only date-named pages) and `session_days` (a docket row is dated by the date it writes);
  - `fetch_rollcalls_db.SUMMARY_SQL`/`HISTORY_SQL`/`VOTE_WORD`;
  - `.claude/hooks/guard.py` (it denies only commands that name the host, and asks before any `wrangler`);
  - preflight's `_night_timer`. `src/checks/suite/` does not exist.

**What I ran** (no network; scripts in `/tmp/claude-0/audit/wf16/final/scripts/`):
- `days.py`: House sitting days 2019–2026 from `records/rollcalls/` in git.
- `load.py`: the SQL load this design's cadence would put on every 2025–26 sitting day. It uses the session recordings' own start and end (`collected/videos/`, in git) and the roll calls.

**Web, read today:** Cloudflare's Wrangler configuration page (updated 20 October 2026) for which keys environments inherit, and a search on GitHub's answer to a dispatch with an undeclared input. Every other platform fact is as the reviews re-read and dated it (Sources, at the end).

**No request** went to gc.nh.gov, gencourt, the General Court's SQL host or YouTube. No follow database was touched, and nothing in the repository was edited.

**Labels:** **measured** (I or a review ran it), **read** (code, docs or a cited page), **guess**.

---

## 0. The design on one page

**One new running program, one store, two read-only addresses.**

```
YouTube Data API ──┐                                  ┌─► GET /api/live/streams       Live Now's own data (not public API)
                   ├─► Worker graniterecord-live ─────► R2 bucket graniterecord-live
PublicSQL (TDS)  ──┘   cron every 2 minutes, no address  └─► GET /api/live/votes/<date>  public, provisional (API v1, beta)
 SELECT only, never gc.nh.gov       ▲                         ▲  two read-only Pages Functions
                                    │ control.json             │
                          a person (wrangler … --remote)     the night: /live, live/schedule.json,
                                                               /session/<B>/today, session-day pages
```

1. **Worker `graniterecord-live`** (`workers/live/`). It has no address, and its cron runs every 2 minutes. It decides on New Hampshire's clock what each run does.
   - **YouTube:** which House and Senate streams are live.
   - **The General Court's public SQL database** ("PublicSQL"): while a chamber sits, it reads that day's roll calls, the ballots of new ones and the docket's tally lines. It speaks SQL Server's protocol (TDS) itself, over `cloudflare:sockets`, with a client of about 250 lines and no dependencies.
2. **R2 bucket `graniterecord-live`**, private.
   - The Worker writes `state.json`, `streams/<date>.json` and `votes/<date>.json`.
   - **A person writes `control.json`, the one switch.** The Worker only reads it.
3. **Two read-only Pages Functions** on the existing project: `/api/live/streams` (the page's data) and `/api/live/votes/<date>` (public).

**Secrets: two.** A second YouTube key, restricted to the Data API, in the same Google project; and a Healthchecks URL. There is **no SQL secret**: the login is the one the General Court publishes, already in `probe_db.py`. There is **no GitHub job, no GitHub token and no Cloudflare token**.

**What it never does:**
- ask gc.nh.gov;
- read the site, or write the record;
- keep YouTube data past 30 days, or serve it as public API;
- work out whether a motion carried;
- quote a caption;
- run more than 1,200 database statements in a New Hampshire day.

**What the owner gets in January:**
- `/live` with every live House and Senate stream, each titled with its committee and that day's calendar card below it. It is linked beside Recent Session Days.
- House roll calls with names, on Live Now's session card and on **`/session/H/today`**, within one 2-minute read of reaching PublicSQL. The IT office says that is immediate; the first sitting measures it.
- The Senate's tally from the clerk's docket during the sitting. Senate names follow once the Senate saves them, including saves the next morning.
- A public, provisional live votes file in the same shape as the night's record.
- Each morning, the night's record replaces every live copy, roll call by roll call.

**The one gate before any sitting.** In mid-November the deployed Worker runs a test (§2.7). It shows whether PublicSQL accepts Cloudflare's addresses without forcing encryption, which a Worker cannot do inside TDS. If the test fails, only the votes half moves to a named fallback (§2.8). Live Now is unchanged.

**What came from where:**
- **From B:** the base itself; files split by source; the record winning by roll-call id in the page; the generated constants module; the cron every 2 minutes; the season heartbeat; the daily budget; nvarchar casts; the bounded connect; Healthchecks on every run; the replay; the compact ballot string.
- **From A:** no clock cap; the Senate docket filter; re-reading the day whole; `maxResults=50` and search on both channels; `'YYYYMMDD'` literals; compare-and-set; LOGIN7's application name; synthetic YouTube fixtures; a message for each cause; the path whitelist; a test against a fixed past sitting; holds that expire; a YouTube-only first branch.
- **New, from the reviews:**
  - `control.json` as the one person-written switch;
  - the host bound only in production, with a loopback guard;
  - `/session/<B>/today` instead of forecast pages;
  - a lease before any write;
  - the night's window honoured by the Worker;
  - preview binding accepted explicitly, behind a read-only facade.

---

## 1. Live Now

### 1.1 How streams are found

**Channels:** House `UCxqjz56akoWRL_5vyaQDtvQ` and Senate `UCjBZdtrjRnQdmg-2MPMiWrA` (`fetch_channel_index.CHANNELS`). They reach the Worker only through the generated `live.gen.js` (§6.2). Each uploads playlist is the channel id with `UC` changed to `UU`; shadow confirms this once with `channels.list` (1 unit).

**What each run asks YouTube.** The window is weekdays 07:00–20:00 New Hampshire time. **Read** (`streams.md` §3): every stream start on record, 2020–2026, falls inside it.

| When | Calls | Units |
|---|---|---|
| In the window, every run (390 runs) | `playlistItems.list?part=contentDetails&maxResults=50` on each uploads playlist (2 units: 50 costs what 10 does). Then one `videos.list?part=snippet,liveStreamingDetails,status` (≤ 50 ids, 1 unit) for: ids not seen before; ids kept as `upcoming` with `scheduledStartTime` from 2 hours ago to the end of today; ids now `live` | 3 a run, **1,170** |
| The first run in the window each day | one `videos.list` over every upcoming id kept in `state.json`. This refreshes them within III.E.4.d's 30 days and drops any that were cancelled | 1 per 50 ids |
| Weekdays outside the window | every 10 minutes, `videos.list` for ids still live (nothing when none is); every 30 minutes, discovery as above | ≈ 80 |
| Weekends | discovery every 30 minutes; ids still live every 10 minutes | ≈ 150 |
| **Backstop, both channels**, in the window | `search.list?channelId=…&eventType=live&type=video` every 30 minutes, from its own allowance of 100 calls a day | **52 of 100** |

- **A weekday is about 1,270 of the project's 10,000 units, plus 52 searches.** The night's `livestreams.py` adds 2–20 units from the same project. Quota resets at midnight Pacific.
- **Pre-scheduled streams are not lost** (this answers the works and safe reviews). A House stream scheduled weeks ahead keeps its scheduling-date place in the uploads list until it ends. `streams.md` measured the 15-entry feed pushing out "Capital Project Overview Committee (11/16/2026)". So:
  - the Worker keeps every `upcoming` id it has ever seen in `state.json`, with its `scheduledStartTime`, until that day has passed. At most 30 days, under III.E.4.d;
  - each first run of the day re-asks them;
  - the newest 50, not 10, are read;
  - search covers the House too.
- **The search backstop stays on, per channel,** until shadow and the first session weeks show that the uploads list carries an unscheduled stream while it is live (`streams.md`'s main unknown). Then it is dropped for that channel.
- **Status** is `livestreams.status_of` ported to JavaScript:
  - `live` or `upcoming` from `snippet.liveBroadcastContent`;
  - `ended` once `liveStreamingDetails.actualEndTime` exists (the page wants the end, so a `P0D` still reported after the end counts as ended);
  - `embeddable` from `status.embeddable`.
  - A preflight check runs the Python and the JavaScript on the same **synthetic** answers (§7.1).
- **Failures:**
  - Every call times out at 8 s (`AbortSignal.timeout`).
  - `quotaExceeded` holds the YouTube half until the next midnight Pacific.
  - `keyInvalid` or `forbidden` holds it for the rest of the New Hampshire day and sends Healthchecks `/fail`.
  - Five failed runs in a row also send `/fail`.

### 1.2 Matching a stream to its committee and today's agenda

**The night writes `site/live/schedule.json`** from `build_calendar.py`'s own `weeks` and its `cal_days` renderer, so a card is the Calendar's card byte for byte. It covers today and the next four weekdays:

```json
{"built": "2027-01-07", "tz": "America/New_York",
 "days": {"2027-01-07": [
   {"id": "H|Finance|2027-01-07", "chamber": "H", "kind": "standing",
    "name": "House Finance", "href": "/committee/H09",
    "card": "<the card's HTML exactly as cal_days draws it>",
    "match": ["house finance", "finance"]}]},
 "next": {"date": "2027-01-08", "name": "Senate Judiciary"}}
```

- `kind` is `standing`, `study`, `floor` or `conference`.
- `match` is computed in Python with `build_manifest`'s `canon`/`resolve_committee` and the stems that committee's past recordings carried. For a committee of conference, it is the bill numbers (`BILL_TITLE_RE`).
- **There is no `sittings` forecast** (A's, dropped; §4.2 says why).

**The page matches; the Worker never reads the site.** The page's stem function:
1. strips `(MM/DD/YYYY` (or `(MM/DD/YY`) and everything after it;
2. lower-cases;
3. turns `&` into `and`;
4. collapses punctuation.

Preflight holds it equal to the Python stem on every title in `collected/videos/`, including the unclosed "Committee of Conference on SB 534  (05/22/2026".

**Session streams:**
- **The rule:** a stem that *begins* "house session" or "senate session".
- **Measured** (B): 172 session titles in the committed indexes, and no other title begins that way. "Full Committee Work Session" does not.
- **Measured here:** Organization Day streams are titled the same way, "House Session (12/04/2024)" and "Senate Session (12/04/24)".
- This one pattern, from `live.gen.js`, both draws the session card and lets the votes half read while a chamber sits.

**Unmatched streams** keep YouTube's title without its date, with no card under them. **A meeting with no stream found** is listed as such (§1.4). Live Now must show study committees, which the Calendar hides by default (`plan.md` D14).

**The agenda under a session stream:**
- It is the Calendar's floor card when the Calendar has one for today. For the Senate it often does, because the Senate enters floor rows ahead.
- Otherwise it is a link to the chamber's session-day list. A morning-of House agenda (the calendar's session notice and its bills) is a follow-up, not a dependency (§10).

### 1.3 What is stored for streams

**`streams/<YYYY-MM-DD>.json`** (the New Hampshire day) is rewritten on every run that asked YouTube:

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

- `next_check` is when the Worker will next look: 2 minutes ahead in the window, 10 or 30 outside it.
- Today's ended streams stay in the file, for "Earlier today".
- `seen` is the shadow measurement: when each path first saw the stream, against YouTube's own `actualStartTime`. It lives in the day's file and goes with it at 30 days.
- With `control.json` saying `"youtube": "off"`, the Worker asks nothing and writes the day's file once with `"problem": "off"`.

### 1.4 The page `/live`

**The night writes `site/live.html`** with today's meetings already in the HTML (the cards from `schedule.json`), both channels' links and a `<noscript>` line. It works with no script and no live data, and never waits on anything.

**`live.js`** is its own small script, used by `/live` and by the session pages (§4). It:
- fetches `/api/live/streams` on load and every 60 seconds while the tab is visible (Page Visibility API), with `If-None-Match`;
- pauses while the tab is hidden, and fetches at once when it returns.

**Each live stream is a card, keyed by video id and updated in place,** so a player someone opened keeps playing. Up to 16 can be live at once (measured peak). A card has:
- the Calendar's name ("House Finance"), or YouTube's title without its date;
- "Live since 10:02 a.m.";
- the site's **press-to-play** stub (`<button data-embed="vid||">`): no thumbnail and no request to YouTube until it is pressed, on `youtube-nocookie.com`, with `origin=` added;
- "On YouTube";
- **that meeting's calendar card below it.**

**Then three lists:**
- "Scheduled to stream today";
- "On today's calendar — no stream found (checked 2:14 p.m.)";
- "Earlier today", each with "On YouTube".

**Wording states what was checked, never a fact about the world** (safe review). The page never writes "not streaming" or "nothing is live".

| Data | The page says |
|---|---|
| Fresh, nothing live | "No stream found right now (checked 2:14 p.m.)", then the rest of today, or `next` |
| Stale: now is past `next_check` by more than 5 minutes (so a quiet evening checked every 30 minutes is never stale), or the request fails | "Live status has not been checked since 10:42 a.m." over the static list |
| The file says `problem: "off"` | "Live status is turned off" over the static list |
| 404 (no binding: forks, local builds) | "Live status is not available" over the static list |

**The session card** (a "House Session" or "Senate Session" stream) carries:
- the stream;
- the agenda (§1.2);
- the day's live votes (§4.1);
- a link to `/session/<B>/today`.

**Spanish:** the strings go into the catalogue and are translated when Spanish is switched on.

### 1.5 The home page

- **Where:** one line under `#session` (Recent Session Days, `build_pages.home_body`/`session_line`), where the owner asked: **"Live Now — 7 meetings today"**, linking to `/live`.
- **Cost:** the night writes the count into the HTML, so a home visit makes **zero requests** for it.
- **No stale count:** the line carries its date, and three lines of inline script drop the count (keeping the link) when that date is not today in New Hampshire. So a missed night never shows yesterday's count.
- **On days with no meetings** it reads "Live Now".
- **Also in this branch:**
  - `/live` goes into `find.json`;
  - `home.json`'s dead `status["live"]` goes;
  - `livestreams.py`'s stale quota comment is corrected.
- **Left out:** `plan.md`'s second line near the top on phones (D4), which can be added later at no request.

### 1.6 The committee page: its live stream at the top

**Asked by the owner, 29 October 2026.** When a committee is streaming, its own page (`/committee/<code>`, the study committees' `/committee/ss<id>` too) shows the stream at the top, not only on `/live`.

**What it reuses, and what it adds.** No new endpoint, no Worker change, no new data. It reads `/api/live/streams` (§5) and matches with the same stems `schedule.json` carries (§1.2). It adds one hook the night writes into each committee page, and a mode of `live.js` (branch 5) that fills it.

**One source of truth (the owner, 29 October 2026).** A committee page says a stream is live from the same data Live Now uses: `/api/live/streams`, matched with the same stem function and the same per-committee stems as `schedule.json`'s `match`. It does not depend on the calendar. A stream that matches the committee lights its page whether or not the meeting was on the calendar.

**The hook (written by the night into EVERY committee and study-committee page, static):**

```html
<section id="live-now" class="lv" hidden
         data-committee="H09" data-chamber="H"
         data-match='["house finance","finance"]'>
  <template class="lv-agenda" data-day="2027-01-07"><!-- today's calendar card, only when schedule.json has one --></template>
</section>
```

- **`data-match`** is the committee's stems: its canonical name and the stems its past recordings carried (`build_manifest`'s `canon` and the committee's rows in `collected/videos/`). The night computes them once. `schedule.json`'s `match` for that committee is held equal to them by preflight, so `/live` and the committee page cannot disagree about which stream is whose.
- **The agenda `<template>`** is written only when today's or the next weekday's calendar has the committee. It carries its `data-day`, and `live.js` uses it only when that day is today in New Hampshire.
- **Nothing in the hook depends on the schedule.** A page whose committee is not on the calendar still lights when its stream is live.
- **It sits outside `app.js`'s render root**, directly above the tabs, so no re-render touches it. In `build_committees.py` and `build_study_committees.py` it is one small function and one call site each, so that a later conflict with the release session's files is trivial.

**What `live.js` does there:**
- **It fetches only inside the Worker's own window:** weekdays 07:00–20:00 New Hampshire time. The window's constants move from `clock.js` into `live.gen.js` (`live_gen.py` is their one source), and the night writes them into `live.js`, so the Worker and the page cannot drift. Outside the window it makes **zero requests**.
- **Inside the window**, it fetches on load and once a minute while the tab is visible, using `If-None-Match` and §1.4's Page Visibility rule.
- **A stream already live at 20:00 keeps the page polling** until that stream ends, or until the Worker stops reporting it (approved 29 October 2026): late sittings and long hearings run past 8 PM. Polling stops at the first answer that does not have that stream live, or one past its `next_check` by more than 5 minutes.
- **The cost of it:** a stream that *starts* after 20:00, or at a weekend, does not light the committee page; it still shows on `/live`.
- A stream is this committee's when its title stem matches one of `data-match` and its chamber is the committee's. Session streams (§1.2) never match a committee.
- While one is `live`, the hook is shown as one card:
  - the heading "Live now", and "Live since 10:02 AM", in the site's own time format (`components.clock` and its JavaScript twin, as the calendar cards print times);
  - the site's own press-to-play stub: `button.pstub` with `data-embed="<video>|0|lv-<video>"` and `data-title` from `recTitle`. The page's one delegated handler builds the player when it is pressed. **Nothing loads from YouTube before a press, and nothing plays without one.**
  - "On YouTube";
  - today's agenda: the `<template>`'s calendar card, with its bills linked, as the Calendar draws it, when the night wrote one for today. **When it did not, the card shows the stream with no agenda, and says nothing about why.**
- A stream `upcoming` within 15 minutes shows the same card headed "Scheduled to stream at 10:00 AM", with no stub.
- **Several of the committee's streams live at once** (a morning and an afternoon session that overlap) are each a card, newest first, keyed by video id.

**Ending cleanly:**
- **The stream ends and the reader never pressed play:** the card is removed and the hook hidden.
- **The reader is watching:** the player stays where it is, and the heading becomes "Ended at 12:14 PM" with one line: "The recording reaches this page's Videos tab after the next nightly update." (Not "tonight's": a frozen or failed night would make that untrue.) It goes when the reader leaves the page.
- **The data goes stale or the request fails** (§1.4's rule, more than 5 minutes past `next_check`): the card is removed unless it is playing. This page makes no claim of its own about live status. It never says "not checked since", "not streaming" or "nothing is live"; those sentences belong to `/live`.
- **A 404 (no binding: forks, local builds):** the hook stays hidden and polling stops.

**The Videos tab (feat/committee-videos), one family, no shared code changed:**
- **Same parts:** `.pstub`, `.pbar`, `recTitle`, the kind chips (`k-hearing` and the rest, same names and colours), and the `.player` box. The live card's own classes are `.lv*`. Nothing `.vw*` and no `vw*` function is used or changed.
- **Survives re-renders:** `live.js` updates the card in place by video id. A playing iframe is never rebuilt. `app.js`'s re-renders cannot reach it, because the hook is outside its root.
- **One plays at a time:** when either player starts, the other is paused with YouTube's `pauseVideo` over `postMessage`. Both iframes carry `enablejsapi=1`, as the stub already builds them.
- **Pausing:** a tab hidden by the page (Page Visibility) pauses nothing; the stream is live and the reader may be listening. The live card is never inside a tab pane, so the Videos tab's rule that "a pane hidden by its tab pauses its frame" does not apply to it.
- **The phone's sticky spot:**
  - The live card is **never sticky**. It scrolls away with the page, as the head does, and the Videos player keeps the one sticky spot.
  - When the reader is on the Videos tab and the live card has scrolled out of view, a one-line bar *inside the Videos tab's sticky strip* says "House Finance is live now", with a "Watch" button that scrolls back to the card. It is part of that strip, not a second sticky element. While the live player is playing, the bar says "Playing live" and the button returns to it.
  - That bar needs a hook (`<div class="lv-strip" hidden>`) in the Videos tab's sticky strip. That is the release session's code, so it comes to them as a described patch of two lines. Until it lands, the card simply scrolls and nothing is sticky.
- **Captions are never quoted**, here as anywhere.

**Study committees and commissions** get the hook from `build_study_committees.py`, the same way, from the Calendar's study rows (Live Now shows study committees; the Calendar hides them by default, §1.2).

**Not covered, and said here:**
- A stream outside the Worker's window (after 20:00, or at a weekend) does not light the committee page.
- Committees of conference have no committee page.

**Words** (catalogue keys, translated when Spanish is on): "Live now", "Live since {time}", "Scheduled to stream at {time}", "Ended at {time}", "The recording reaches this page's Videos tab after the next nightly update.", "On YouTube", "{name} is live now", "Watch", "Playing live".

**Caching and requests:**
- **`/api/live/streams`** answers with `Cache-Control: public, max-age=30`, its `ETag`, and a 30-second copy per data centre through the Cache API. §5 said 15 s until this section; at 30, `/live` and every committee page poll the same cached answer.
- **Every poll is still one Function invocation.** A Pages Function runs before any cache, so the cache saves R2 reads, not invocations. With `If-None-Match` an unchanged answer is a 304 with no body.
- **The volume (guess, labelled so):**
  - In session weeks, suppose 2,000 committee-page views a weekday inside the window, each visible about 3 minutes. That is about 6,000 polls a day.
  - About 22 weekdays a month makes roughly 130,000 Function requests a month.
  - Ten times that is 1.3 M, against the Workers Paid plan's 10 M a month included (Pages Functions are billed as Workers requests).
  - R2 reads stay under 3,000 a day per data centre with readers (one each 30 s, 07:00–20:00).
  - The real counts come from the Cloudflare dashboard after January's first weeks.

**Checks:**
- **`page.test.js` (under `dom_stub.js`):**
  - no request outside the window (weekdays 07:00–20:00), at a weekend, or with no hook;
  - the match takes the committee's own stream and not a session stream or another committee's;
  - a live stream shows one card with a stub and no iframe;
  - pressing builds the player;
  - a refresh keeps the playing iframe;
  - an end removes the card, or keeps the player with "Ended at";
  - stale and 404 remove an unplayed card and say nothing;
  - starting one player pauses the other;
  - the strings "not streaming" and "nothing is live" never appear.
- **Preflight:**
  - the hook sits outside `app.js`'s root;
  - it is on every committee and study-committee page, with `data-match` equal to the committee's `schedule.json` `match` wherever the schedule has the committee;
  - the window `live.js` carries equals `live.gen.js`'s.

**Branch:** `live/committee-player`, after `live/votes`. It builds off dev once feat/committee-videos is merged, needs branch 5's `live.js`, and ships with Live Now's public release (about 9 December). Screenshots at 390 and 1280, light and dark, with a fake live stream from `fake_youtube.js`'s fixtures; adversarial review.

---

## 2. Live votes

### 2.1 Where it runs: TDS in the Worker

**The platform allows it (read; both reviews re-read it):**
- A Worker opens TCP inside a handler, `scheduled()` included.
- Only Cloudflare's own addresses, localhost, private networks and port 25 are blocked.
- A cron under an hour gets 30 s of CPU and 15 minutes of wall time.

**What a Worker cannot do (read, MS-TDS PRELOGIN):**
- carry TLS inside TDS packets. `startTls()` works only on a socket opened as `starttls`.
- So the client declares **`ENCRYPT_NOT_SUP`**. A server that forces encryption answers `ENCRYPT_REQ` and ends the connection.
- Today's fetchers cannot show the setting: `Encrypt=False;TrustServerCertificate=True` works either way.
- Sending the login unencrypted exposes nothing: the password is the published one.

**Evidence (measured by A and B, against fakes only):**
- Two independent minimal clients (A's 171 lines, B's 158) ran inside workerd through `connect()`, from `fetch()` and `scheduled()`. They logged in and decoded rows.
- tedious 20.3.5 accepted the same fakes, so the fakes speak standard TDS.
- B replayed 11 March 2026 (56 roll calls, 21,952 ballots) through the Worker. All 56 matched the record ballot for ballot.
- **tedious in workerd with `encrypt:true` reported success and sent LOGIN7 in clear.** So a hand-written client that fails closed is the safer choice, not only the smaller one (10 KiB against 2.9 MB).

**The client, `workers/live/tds.js`** (about 250 lines). It starts from B's `tds_min.js`, which already handles `ORDER`, `NBCROW`, `ENVCHANGE`, `INFO`, `ERROR`, `DONE` and replies split over 4,096-byte packets, and adds:
1. **Text columns only.** Every column the SQL returns is cast to `nvarchar` (§2.2), so the client accepts exactly one column type, NVARCHAR (0xE7), and treats any other type as an error, never a guess. This answers the works review: SQL Server sends fixed-length INT4 or DATETIME for columns it infers are not null, and A's parser would have failed on them. A test sends a fixed-length INT4 column and expects a `type` error.
2. **Every step bounded.** Connect races `socket.opened` against a deadline (B measured an unroutable address hanging past 40 s before this). Connect and login get 15 s, each statement 15 s, and the whole SQL part of a run 45 s.
3. **LOGIN7 names itself:** application `graniterecord-live`, host `graniterecord.org`, so the General Court's administrators can see who is connected (A).
4. **TDS older than 7.2 is refused,** read from `LOGINACK`, because older versions size `DONE`'s row count differently (A).
5. **A loopback guard** (safe review, high): `connect()` refuses any host but `127.0.0.1` or `::1` unless `env.ENV === "production"`. Only `[env.production.vars]` sets `ENV` (§6.2). The host itself is never in code (§6.2).

### 2.2 The queries

There are three SELECTs, and nothing else runs (plus `SELECT @@VERSION` in test mode only). They read only `RollCallSummary`, `RollCallHistory`, `legislators` and `Docket` on `NHLegislatureDB`. These are the columns `fetch_rollcalls_db.SUMMARY_SQL`/`HISTORY_SQL` and `dayfiles_from_db` already use, which the works review found in `db/_columns.json`.

**Rules for every statement:**
- **Every output column is `CAST(… AS nvarchar(n))`,** and dates are `CONVERT(nvarchar(19), x, 126)` (ISO 8601). This is the existing fetchers' habit (they cast to `varchar`).
  - It needs no source types: `db/_columns.json` has names only (works review), so A's plan to read types from it is dropped.
  - Text casts are legal from every type.
- **Literals** are integers the Worker made with `Number()`, and dates written `'YYYYMMDD'`, which SQL Server reads the same under every `DATEFORMAT` and language (A; B's `'2027-01-07'` is not safe under DMY). One function builds them. TDS `SQL_BATCH` has no parameters, which is why. Nothing a reader sends reaches SQL.
- **No `;`, no comment, no `*`.**

Below, `@Y` stands for the session year, `@D` for today, `@D1` for tomorrow, `@W` for the start of the window (today, or 14 days ago), `@D21` for 21 days ago, and `@MDY` for today as `MM/DD/YYYY`.

**Q1: summary rows dated in a window, both chambers.**

```sql
SELECT CAST(s.LegislativeBody AS nvarchar(1)), CAST(s.VoteSequenceNumber AS nvarchar(8)),
       ISNULL(CONVERT(nvarchar(19), s.VoteDate, 126), ''),
       CAST(ISNULL(s.CondensedBillNo, '') AS nvarchar(20)),
       CAST(ISNULL(s.Yeas, 0) AS nvarchar(8)), CAST(ISNULL(s.Nays, 0) AS nvarchar(8)),
       CAST(ISNULL(s.Present, 0) AS nvarchar(8)), CAST(ISNULL(s.Absent, 0) AS nvarchar(8)),
       CAST(ISNULL(s.Question_Motion, '') AS nvarchar(400)),
       ISNULL(CONVERT(nvarchar(19), s.DateModified, 126), ''),
       CAST(ISNULL(s.UserName, '') AS nvarchar(40))
FROM RollCallSummary s
WHERE s.SessionYear = @Y AND s.VoteDate >= '@W' AND s.VoteDate < '@D1'
ORDER BY s.LegislativeBody, s.VoteSequenceNumber
```

- **The window is today on a hot run.** Any run whose last wide read is 10 minutes old or more reads **the last 14 days** instead: every warm and heartbeat run, and one hot run in five.
- **There is no sequence cursor** (works review, B low). Re-reading the window whole catches the following:
  - rows the clerk edits or re-keys. 28 of 885 House roll calls were re-keyed by `hadmin` in 2024–26, and S 49 of 2026 had its bill corrected;
  - Senate rows saved out of order. 5 of 208 in 2025–26 were saved after a higher-numbered one, among them 2026 S 9 and S 11, saved on the morning of 30 January; 84 of 379 in 2022–24;
  - Senate rows saved on a later day: 117 of 208 (56%) in 2025–26, which A would have missed.
  - With no cursor, there is nothing to rebuild if `state.json` is lost.
- **Size (measured on 2025–26):**
  - at most 56 House and 25 Senate rows on one day;
  - at most 127 rows (both chambers) in any 14-day window ending on a roll-call day;
  - a mean of 54 characters a row in these fields.
  - So a wide read is about 15 KB, and a hot read under 10 KB.

**Q2: ballots, only for roll calls that need them.**

```sql
SELECT CAST(h.LegislativeBody AS nvarchar(1)), CAST(h.VoteSequenceNumber AS nvarchar(8)),
       ISNULL(CAST(l.PersonID AS nvarchar(12)), CAST(ISNULL(h.EmployeeNumber, '') AS nvarchar(12))),
       CAST(ISNULL(h.Vote, 0) AS nvarchar(4))
FROM RollCallHistory h LEFT JOIN legislators l ON l.Employeeno = h.EmployeeNumber
WHERE h.SessionYear = @Y
  AND ((h.LegislativeBody = 'H' AND h.VoteSequenceNumber IN (14,15))
    OR (h.LegislativeBody = 'S' AND h.VoteSequenceNumber IN (3)))
```

- **Asked for** a roll call that is new; one whose set is incomplete (its Yea and Nay counts differ from the summary's); or one whose tally or `DateModified` changed.
- **An incomplete set** is asked again on the next run, and after two tries at most every 10 minutes.
- **Limits:** at most 20 roll calls per statement and one statement per run. Never for a roll call dated more than 14 days back.
- **The join** is `HISTORY_SQL`'s own, which its `--check` proved line for line. The id falls back to the employee number, as the site's own rule does (`build_site_v2.build_legislators`).

**Q3: the docket's roll-call tally lines for today, both chambers, on hot and warm runs.**

```sql
SELECT CAST(d.LegislativeBody AS nvarchar(1)), CAST(ISNULL(d.CondensedBillNo, '') AS nvarchar(20)),
       ISNULL(CONVERT(nvarchar(19), d.StatusDate, 126), ''),
       CAST(ISNULL(d.statusorder, 0) AS nvarchar(8)),
       CAST(CAST(d.Description AS nvarchar(max)) AS nvarchar(1000))
FROM Docket d
WHERE d.SessionYear = @Y AND d.Description LIKE '%RC [0-9]%'
  AND (   (d.StatusDate >= '@D' AND d.StatusDate < '@D1')
       OR (d.StatusDate >= '@D21' AND d.Description LIKE '%@MDY%'))
ORDER BY d.LegislativeBody, d.CondensedBillNo, d.statusorder
```

- **One filter for both chambers** (works, safe and simple reviews: B's `StatusDate = today` misses the Senate). `StatusDate` is when a line was *entered*. The Senate creates floor lines days ahead and fills them in during the sitting (`votes.md`: 600 lines, for example created on 9 February for the 19 February sitting). `session_days` dates a row "by the one the row writes", for example "…; 05/15/2019". So a line is taken if it was entered today, or if it was entered in the last 21 days and carries today's date in its text.
- **`RC` is matched only when digits follow:** the General Court's key defines bare "RC" as Regular Calendar (A).
- **Re-read whole each time:** the view has no last-modified column (`dayfiles_from_db.docket_rows`). That means tens of lines.
- **Cost** is unmeasured: `Docket` is a 317,811-row view over two source databases with unknown indexes. The November test times it (§2.7). If it takes more than 1 s, Q3 runs on one hot run in five.

### 2.3 When it reads

**There is one connection per run that has reading due, for both chambers, closed at once.** A socket cannot outlive an invocation. Each chamber is in one of four states, worked out every run:

| State | When | Reads |
|---|---|---|
| **Hot** | the chamber's session stream is live (or scheduled to start within 15 minutes), **or** a roll call of that chamber dated today was first seen in the last 45 minutes | every run (2 min): Q1 + Q3, and Q2 when needed |
| **Warm** | for 5 hours after the chamber was last hot, never past 23:59 New Hampshire time | every 10 min: Q1 (wide) + Q3 + Q2 when needed |
| **Heartbeat** | weekdays from the end of the night's window (08:30 EST, 09:30 EDT) to 18:00, from 1 January to 30 June, and on weekdays in the 14 days after any day the chamber was hot. Only when neither hot nor warm | every 15 min: Q1 (wide) alone, a few KB. A roll call dated today makes the chamber hot |
| **Off** | otherwise | nothing |

**No clock cap** (works review, high). Reading goes on while the session stream is live or roll calls keep coming, whatever the hour. The 5-hour warm tail covers the Senate's same-day saves: a median of 74 minutes and at most 287 minutes after its stream ends (`votes.md`).

**Measured** against the cap B had: 4 House days in 2019–2026 had roll calls at or after 20:00.

| Day | First vote | Last vote | Roll calls | At or after 20:00 |
|---|---|---|---|---|
| 12 March 2020 | 09:53 | 23:58 | 49 | 17 |
| 16 March 2022 | 09:26 | 21:36 | 47 | 10 |
| 17 March 2022 | 09:23 | 21:15 | 30 | 4 |
| 11 March 2026 | 09:23 | 20:46 | 56 | 7 |

On 11 March 2026 the session stream ran 08:58–20:49.

**Votes do not depend on YouTube** (the works, safe and simple reviews on A). Two independent signals each start reading:
- the session stream (YouTube);
- the heartbeat (the General Court's own first roll call).

The Worker reads nothing from the site, so A's contradiction about `schedule.json` is gone. The heartbeat's cost on a non-sitting weekday is measured below.

**What a sitting is not detected by:**
- outside January to June, a sitting YouTube does not report (a veto day, a special session) shows its votes the next morning;
- a Senate sitting YouTube misses gets no live tally (Q3 needs hot), though its roll calls still arrive by the heartbeat once saved.

Both are said here rather than hidden.

**The night's window** (safe review, medium). `refusal.window_check` keeps a stood-down laptop's queries of this host out of `refusal.NIGHT_WINDOWS`, so that the laptop and the night never query it at once. The Worker is a third machine, so it honours the same windows, which it receives from `live.gen.js`:
- Heartbeat and warm reads never start inside a window.
- Hot reads inside a window happen only for a chamber whose **session stream is live**. That means a sitting already under way before 09:30 EDT on a morning the night runs late.
- That is the one case where two machines query PublicSQL at once. It rests on the IT office's answer of 15 September ("No problem hitting PublicSQL during a session as it doesn't touch the website"), not on a reading of the project's rule. It is listed for the owner (§10, default 2).
- The Monday weekly window (04:00–06:30 UTC) never meets a reading state.

**The daily budget** (`votes.md`'s rule, which A lacked). `state.json` counts connections, statements and rows per New Hampshire day. At **600 connections, 1,200 statements or 150,000 rows** the votes half holds until the next day, the files say so, and Healthchecks gets `/fail`. The limits sit about 40% above the heaviest day of 2025–26, and about 28% above the estimate for 12 March 2020.

**Measured load**, from `scripts/load.py` (the session recordings' real start and end, the roll calls, the rules above) and `scripts/days.py`:

| Day | Connections | Statements |
|---|---|---|
| 11 March 2026, the heaviest of 2025–26 (stream 08:58–20:49, 56 roll calls) | 395 | 846 |
| 5 June 2025 | 372 | 799 |
| 12 March 2020, to 23:58 (no recording exists; the span is taken as the first vote −30 min to the last +15 min) | ≈ 445 | ≈ 939 |
| A mean sitting day of 2025–26 (40 days) | ≈ 215 | ≈ 450 |
| A non-sitting weekday, January–June (heartbeat) | 34–38 | 34–38 |

Over a year that comes to roughly 9,000 statements on sitting days and 4,000 on heartbeat days (guess, from the two years measured). Each statement is small: today's rows, tens of docket lines, or one batch of ballots.

### 2.4 The merge

**The day's file is `votes/<date>.json`, filed under each roll call's own `VoteDate`.** The Senate's `VoteDate` is midnight of the sitting day, so a Senate save the next morning updates the sitting's file (B).

**Roll calls are keyed by `2027-H-14`:**
- Fields are updated in place.
- `first_seen` is set once and never moves.
- **Never drop what was shown:**
  - a roll call already in the file stays;
  - if three reads in a row lack it, it gains `"note": "no longer listed by the database at 14:12; the record will settle it"`. This is CLAUDE.md's "a writer of a derived file, run on a subset, destroys the rest", applied to one day.

**Docket lines:**
- **Parsing:** `RC (\d+)-(\d+)` for the House and `RC (\d+)Y-(\d+)N` for the Senate.
- **The outcome** comes from the abbreviation beside the tally: `MA` Motion Adopted, `MF` Motion Failed, `AA`/`AF` Amendment Adopted/Failed, `ML` Motion Lost, from `records/docket_abbrev.json` through `live.gen.js`. Words not in the key are kept as written, with the outcome `null`.
- **Matching a line to its roll call:** by chamber, bill, yeas and nays, pairing `statusorder` with `seq` order when one bill has two equal tallies. This matched 553 of 558 House tallies and 205 of 208 Senate tallies (`votes.md`).
- **A Senate line with no saved roll call yet** stands as a tally. When the roll call arrives, the tally is attached to it.
- **The Worker never computes "passed".** Thresholds and two-thirds votes are the night's (`vote_passage.py`).

### 2.5 Ballots to members

- **Each roll call's ballots** are one character per member: `Y` Yea, `N` Nay, `E` Excused, `X` Not excused, `P` Presiding, `.` no vote recorded. `VOTE_WORD`'s codes 1, 2, 3, 4 and 6 map to the first five; 0, 5 and 7 are no vote recorded.
- **The string is aligned to `members[body]`,** a list of ids that only grows within a file.
- **Measured** (B): 11 March 2026 comes to 36.9 KB raw and 5.6 KB gzipped, against 9.7 KB gzipped as id lists.
- **Names and parties come from the site's own `/legislators.json`,** which has the person's corrections applied. So a live ring and the next morning's ring use the same party for the same member. A's separate `people.json` is not built (simple review).
- **An id the roster lacks** is counted and shown, as "2 members not yet on this site's roster", never dropped.
- **Excusals are labelled provisional:** 528 House ballots changed a median 117 hours after the vote in 2026 (`votes.md`).

### 2.6 How it fails safe

**One person-written switch, `control.json`, in the bucket** (safe review, high, and simple review, medium).
- **What it holds:** `{"youtube": "on"|"off", "sql": "off"|"test"|"on"}`.
- **Who writes it:** only a person. The Worker reads it at the start of every run and never writes it.
- **When it is missing or unreadable:** YouTube on, SQL off. That is shadow, and it is the safe default.
- **Ready-made files** are in the repository as `workers/live/control/{sql-off,sql-test,on,all-off}.json`. One command switches, for example:

  ```
  npx wrangler r2 object put graniterecord-live/control.json --file workers/live/control/sql-off.json --remote
  ```

  **`--remote` is required:** wrangler 4.148's `r2 object` commands default to local storage (safe review, measured in `wrangler-dist/cli.js`). Preflight fails if any `wrangler r2 object` line in `workers/live/README.md` lacks it.
- **The Worker confirms what it is honouring** in every Healthchecks ping ("sql off by control.json, uploaded 2027-01-07 11:02") and in the files' `status`. So a person sees the stop take effect within 2 minutes.
- **There is no second switch:** neither a `wrangler.toml` var nor a hold the person writes.

**Holds the Worker writes, in `state.json`.** None needs a person to clear it; each ends by the next New Hampshire day, as `probe_db` learned.

| What happened | The Worker | Healthchecks |
|---|---|---|
| Connection refused or timed out | 3 in a row: hold 30 minutes, then one try; failing again holds the votes half for the rest of the day | `/fail` when the day's hold begins |
| `Login failed` (18456), but not 4060 ("Cannot open database", `probe_db.login_refused`'s distinction) | holds for the rest of the day. It lifts at once if the published credentials in `live.gen.js` change (the hash `probe_db._login()` uses). A one-hour lockout on their side therefore costs one day at most, never for good | `/fail`: "the published password may have changed; read the PDF again" |
| `ENCRYPT_REQ` | holds for the rest of the day, and tries once a day after. The Worker cannot read this host, and §2.8 is the decision | `/fail` each day |
| A statement fails on an open connection (renamed column, timeout, a `type` error) | that statement is skipped; 3 in a row hold the day | `/fail` on the hold |
| The budget is reached | holds until the next day | `/fail` |
| A person's `control.json` | honoured at the next run | named in every ping |

**Every state has its own sentence on the page** (safe review, medium on B). The file's `status.problem` is a code, and the page maps each code to its own words. None blames the General Court for the Worker's own stop.

| `status` | The page says |
|---|---|
| `reading`, fresh | "Read from the General Court's database at 10:43 a.m." |
| `reading`, rows 0 | "No roll calls read yet today (read at 10:43 a.m.)". For the Senate it adds "the Senate enters its roll calls after it rises". |
| `connect` | "Votes last read at 10:42 a.m.; the General Court's database could not be reached since." |
| `login` | "Votes last read at 10:42 a.m.; the database has refused the published login since." |
| `encrypt` | "Live votes are off: the database asks for an encrypted connection this site's reader cannot make." |
| `query` | "Votes last read at 10:42 a.m.; a query has failed since." |
| `budget` | "Live votes reached today's limit on queries and stop until tomorrow." |
| `off` | "Live votes were turned off by this site at 11:02 a.m." |
| `day_over` | "Reading stopped for the day at 10:12 p.m." |
| Past `next_read_by` by more than 5 minutes | "Not read since 10:42 a.m." (and nothing else; the reason may be the Worker itself) |
| An unknown code | the same, "Not read since …" |
| No file for today | "No roll calls read today." |

Every sentence ends with: "Every vote reaches this page with tomorrow morning's record." The page never shows an empty list without one of these, and never says "no votes" on a failed read.

**Healthchecks:**
- A new check with a 2-minute period and a 10-minute grace, pinged every run. The body carries the run's codes, the control state and the day's statement count.
- `/fail` goes out on:
  - a hold beginning;
  - the budget;
  - five YouTube failures in a row;
  - three runs in a row finding another run's lease (§3.3);
  - a run that had something due and wrote nothing ("silence is not success").
- Per-run codes also go to Workers Logs (`[observability] enabled = true`, as on the other two Workers). There is no log object in the bucket: R2 has no append, so A's appended `log/*.jsonl` would be a read and full rewrite each run (works review).

**First House days are often keyed by hand** (2019, 2023, 2025, `votes.md`). If 6 January 2027 is one, the page says "No roll calls read yet today", which is true. A plain line under it adds: "The House clerk sometimes enters the first day's roll calls later."

### 2.7 The November test: the one gate

`control.json` set to `sql-test`, after the owner's yes and before any sitting.

**Day 1**, the first run between 10:00 and 16:00 New Hampshire time on a weekday (outside every night window), makes one connection. It records the PRELOGIN encryption answer and version, `LOGINACK`'s TDS and server version, and `SELECT @@VERSION`. Then it runs Q1, Q3 and Q2 exactly as in session (Q2 in 3 statements of ≤ 20 roll calls) for **11 March 2026**: the busiest House day, with votes to 20:46. It records each statement's time and bytes, and writes `test/2026-03-11.json` in the live file's shape.

**Day 2:** the same for **19 August 2026**, veto day in both chambers, which tests the Senate's saves and the docket's text dates.

**Later weekdays:** one connection that logs in and closes, recording connect and login times. That is about 20 connections, which shows reachability from whichever Cloudflare location runs the cron.

**The past-sitting reads run once each** (safe review, low on A), so the total is about 22 connections and 14 statements before the session. In test mode nothing else reads the database: no hot, warm or heartbeat reads.

**The comparison is offline.**
- The person downloads the test files:

  ```
  npx wrangler r2 object get graniterecord-live/test/2026-03-11.json --file … --remote
  ```

- `node tests/live/compare_test.mjs` then compares every roll call's tally, and every ballot by vote, with `records/rollcalls/*_2026.txt` in git. It needs no kit.
- Q3's lines are compared with the kit's `Docket.txt` on the laptop.

**Go:**
- the server does not require encryption;
- connections succeed from Cloudflare;
- both comparisons are exact;
- Q2 and Q3 each take under 2 s. Q3 over 1 s means "one hot run in five" (§2.2).

The person then puts `on.json` on 1 December, so that Organization Day (2 December) runs the whole sitting path before the pages are public. No roll call has ever been taken on an Organization Day, so the file must end the day with none.

**No-go:** the votes half needs §2.8, which is the owner's separate decision.

**A courtesy note to the IT office before Day 1** (B's Q6; default yes) states the pattern (§10, default 3) and that it comes from Cloudflare's addresses rather than GitHub's.

### 2.8 The fallback if the gate says no (named, not built)

This is used only if the test shows forced encryption or a refusal of Cloudflare.
- **The workflow:** `.github/workflows/live-votes.yml`:
  - `workflow_dispatch` with one input, `sitting_date`;
  - `windows-2022`;
  - three jobs chained with `needs:`, each with `timeout-minutes: 350`, which covers a 17-hour day without dispatching itself again. GitHub's limits page: "Each job in a workflow can run for up to 6 hours"; a workflow run may last 35 days;
  - `permissions: contents: read`;
  - concurrency group `live-votes`.
- **What it runs:** `src/live/poll_votes.py`, through `probe_db`'s bridge, hold and `window_check`, with the same three statements. Preflight holds the Python and JavaScript SQL text equal. It writes `votes/<date>.json` through R2's S3 API.
- **Cost:** free. The repository is public (`gh api`: `"visibility": "public"`), and standard hosted runners are free for public repositories (GitHub billing page).
- **Started by the live Worker** when a chamber becomes hot. `workers/night-timer/` is **untouched** (safe and simple reviews: its `scheduled()` ignores `event.cron`).
- **Guards, because a fine-grained token with Actions write cannot be limited to one workflow:**
  - the Worker's dispatch URL is a constant naming `live-votes.yml`, and preflight fails if `workers/live/` names any other workflow file;
  - the only input sent is `sitting_date`, which `nightly.yml` does not declare. GitHub answers a dispatch carrying an undeclared input with HTTP 422 (third-party reports, cited in Sources; tested on the branch before anything relies on it);
  - a dispatch of `nightly.yml` with no inputs is a dry run that fetches nothing (`dry_run: true`, `fetch: false` are its defaults, read).
- **New secrets it would add:**
  - in the Worker: a fine-grained GitHub token (Actions read and write, this repository only);
  - in GitHub: an R2 access key id and secret scoped to the live bucket (two secrets).
- **What it loses:**
  - the heartbeat becomes a GitHub cron, which has run 5–7 hours late since 19 October;
  - each first vote of the day waits for a runner to start (a few minutes, guess).

---

## 3. The store

### 3.1 One private R2 bucket

| | R2 (chosen) | KV (`plan.md`'s) | D1 |
|---|---|---|---|
| Consistency | strong: "readers will immediately see the latest object globally" (R2 consistency page, 14 Oct 2026) | "may take up to 60 seconds or more" elsewhere (KV page, 21 Apr 2026) | strong |
| Compare-and-set | `put(…, {onlyIf: {etagMatches}})` returns `null` when the condition fails (R2 Workers API, 31 Jul 2026) | none | in SQL |
| Shape | the live votes file is the API's file | the same | rows |
| Cost here | $0 in the free tier (§3.4) | $0 | $0 |

Consistency decides it. Cron runs land wherever Cloudflare places them, and each run builds on the last one's write.

**Retention:**
- Not public: no custom domain and no `r2.dev`.
- Its own bucket, so the Pages project is never bound to the kit's.
- On its first run after 03:00 New Hampshire time, the Worker deletes `streams/`, `votes/` and `test/` objects older than 30 days (tested). That is YouTube's limit for the streams. The votes are kept the same span, since the record has them by then.

### 3.2 Objects

| Object | Written by | Read by | Kept |
|---|---|---|---|
| `control.json` | **a person only** (`--remote`) | the Worker; neither Function | until replaced |
| `state.json` | the Worker | the Worker | overwritten |
| `streams/<date>.json` | the Worker's YouTube half | `GET /api/live/streams` | 30 days |
| `votes/<date>.json` | the Worker's votes half | `GET /api/live/votes/<date>` | 30 days |
| `test/<date>.json` | the Worker, in test mode | a person | 30 days |

**`state.json` holds no facts about streams or votes beyond what the next run needs** (simple review, on A's state duplicating the votes file):

```json
{"v": 1, "lease": {"run": "…", "until": "2027-01-07T15:03:50Z"},
 "day": "2027-01-07",
 "count": {"connections": 112, "statements": 236, "rows": 9120, "units": 340, "searches": 14},
 "yt": {"upcoming": {"AbCdEfGhIjK": "2027-01-07T15:00:00Z"}, "live": ["…"],
        "discovery": "…", "search": "…", "fails": 0, "held": null},
 "sql": {"H": {"hot_until": "…", "last_hot": "…", "last_rc": "…"}, "S": {"…": "…"},
         "wide": "…", "fails": 0, "held": null, "missing": {"2027-H-14": 1}},
 "test": {"done": ["2026-03-11"]}}
```

**Losing it is harmless:**
- the counts restart (the budget still bounds a day);
- upcoming ids are found again by the playlist and search;
- a hold, if one stood, costs one more failed try.

There is no cursor to rebuild (B's lost-state problem is gone).

### 3.3 One writer at a time

1. Read `state.json` and keep its etag. **A run with nothing due stops here and writes nothing.**
2. If `lease.until` has not passed and it is not this run's, stop. (Three such runs in a row send `/fail`.)
3. Put `state.json` with this run's lease (`until` = now + 110 s), `onlyIf: {etagMatches}`. A `null` means another run took it, so stop.
4. Do the run's work. The YouTube calls are bounded at 8 s each and the SQL part at 45 s.
5. **Only while the lease holds** (under 90 s since step 3), write the changed `votes/` files, then `streams/<date>.json`.
6. Put `state.json` releasing the lease, `onlyIf` the etag from step 3.

**What this answers** (the safe and simple reviews):
- A's compare-and-set protected only `state.json`, while the public files were written first. Here no public file is written by a run without the lease.
- No two runs ever hold SQL connections at once.
- Runs are 120 s apart, so a lease of 110 s never blocks the next normal run.
- The first run ever, with no `state.json`, writes one unconditionally. Two runs at that exact moment is the only unguarded case.

### 3.4 Volumes (guess, from the cadences)

- **Class A writes:**
  - about 1,170 a weekday in the window (a lease, the streams file and a release on each of 390 runs);
  - a few hundred outside it;
  - the votes files on change.
  - That is **≈ 60,000–75,000 a month**, against 1 M free.
- **Class B reads:** 720 state reads a day, plus the Functions' cache misses (at most one per 15 s per data centre with readers). That is **under 1 M a month**, against 10 M free.
- **Storage:** under 20 MB.
- The free tier is per account and shared with the night's private bucket, whose monthly operations are not measured here.

---

## 4. The pages

### 4.1 Live Now's session card

`live.js` fetches `/api/live/votes/<today>` on load. It polls every 30 seconds, with `If-None-Match`, while the tab is visible and the file's `next_read_by` is within 10 minutes; otherwise every 2 minutes.

It draws one list, newest first. Each roll call shows:
- its time, or for the Senate "saved at";
- the bill, linked to its page;
- the question in the record's words;
- the tally;
- the docket's outcome with its source ("Motion Adopted, clerk's docket"), or "outcome not yet in the docket";
- "names: in" or "names follow".

Under the list:
- the §2.6 status sentence;
- "Provisional: the night's record replaces this tomorrow morning; excusals settle days later";
- for the Senate, "Senate names follow once the Senate enters them, usually that afternoon or the next day".

`/live` does not load `app.js`, so it shows tallies as text and links to `/session/<B>/today`. No caption text appears, ever.

### 4.2 `/session/<B>/today`: the session-day page on the day

**This answers the simple review's high finding.** Under B, a House sitting had no session-day page on its own day: the clerk types the House's floor lines during the sitting, so the morning's record does not hold the day. A answered with forecast shell pages, which the safe and simple reviews rejected:
- `build_session_pages.sittings` refuses a sitting after the build ("a mistyped month put a House sitting a month ahead of veto day; neither is a day to publish");
- a snow day would publish a sitting that never happened.

So the night writes **two pages that never move,** `site/session/H/today.html` and `site/session/S/today.html`, every night:
- **Outside every list:** outside `sittings()`, the chamber lists, the sitemap and the next/previous links; `noindex`. `prune()` removes only date-named pages, so these are safe from it (read).
- **What they hold (static):**
  - the heading "The House today";
  - the Calendar's floor card for today if it has one;
  - the link to the chamber's list of session days;
  - a `<noscript>` line: "Today's roll calls reach the House's session pages by tomorrow morning."
- **The date** is the reader's New Hampshire date, worked out by `live.js`, not the build's. **Before 06:00 it shows the previous day**, so a sitting that ran late stays on the page until the night's record has it. A static part dated for another day (the floor card) is hidden.
- **Live parts:**
  - the chamber's session stream, press-to-play, when `/api/live/streams` has one live;
  - the votes list of §4.1, with rings drawn through `app.js`'s `simpleDonut` (the session pages' one vote renderer), from the ballot string and `/legislators.json`'s party;
  - the §2.6 sentence.
- **When the record already has today's sitting** (often for the Senate, which enters floor rows ahead), the night writes the dated page that morning as now, and the today page links to it: "Today's page: /session/S/2027-01-07".
- **Links to it:** Live Now's session card and the dated page.
- **It publishes no sitting:** it says only what was read today.

### 4.3 The dated session-day page: an overlay, with the record winning by id

The night writes a hook into every dated session-day page:

```html
<div id="live-votes" data-day="2027-01-07" data-body="H"></div>
```

**The rule: union by roll-call id** (B):
- The page's own record holds the roll calls the night built.
- Live roll calls whose id the record lacks are added, marked "provisional · read at 10:43 a.m.".
- Once the record has an id, the live copy is not drawn.
- So there is nothing to supersede by hand and no clock rule. A Senate roll call saved the next morning shows on its sitting's page from the moment the Worker reads it, and drops from the overlay the morning the record carries it.

**When it fetches:**
- on load, for a page dated within the last 14 days;
- it keeps polling only while the date is today in New Hampshire;
- older pages ask nothing.

### 4.4 How the night's record replaces the live copy

- **One writer each:** the night never writes the bucket, and the Worker never reads or writes the site. There is no `superseded_by` rewrite and no Worker read of `/data/manifest.json` (simple review, medium on A).
- The record is rebuilt whole every morning as now. The page's id rule means the record wins the moment it holds a roll call.
- **The night's own per-day votes file:**
  - `site/session/<B>/<date>.json`, beside each dated page. This is `plan.md` §3.3 stage 1, which also fixes polish P9: the 570 KB of other bill pages a session day downloads today to draw its rings.
  - It is written in **the same `session.votes` shape** with `"provisional": false`. One schema, `schema/session.votes.json`, holds both, so the page draws both with one function.
  - `prune()` is taught to remove a day's JSON with its page.
- The live files simply expire after 30 days.

---

## 5. The public API's live file

**Public:** `GET /api/live/votes/<YYYY-MM-DD>`, documented on `/developers` as part of API v1, **beta and provisional**, under "Same day, provisional". `/data/manifest.json` lists it as a template with its schema. It carries **no YouTube data**.

```json
{"api": 1, "kind": "session.votes", "date": "2027-01-07", "provisional": true,
 "read_at": "2027-01-07T15:43:02Z", "next_read_by": "2027-01-07T15:45:02Z",
 "status": {"state": "reading", "problem": null, "since": null},
 "source": "The General Court's public SQL database (RollCallSummary, RollCallHistory, Docket)",
 "record": {"H": "/session/H/2027-01-07.json", "S": "/session/S/2027-01-07.json"},
 "members": {"H": ["11463", "960", "…"], "S": ["…"]},
 "rollcalls": [
   {"id": "2027-H-14", "body": "H", "seq": 14, "bill": "2027-2028/HB2", "bill_as_recorded": "HB2",
    "question": "Ought to Pass", "taken": "2027-01-07T15:41:07Z", "saved": null,
    "keyed_by": "voting system", "yeas": 190, "nays": 171, "present": 0, "absent": 39,
    "ballots": "YNNE.Y…", "ballots_complete": true,
    "docket": {"line": "MA RC 190-171", "abbrev": "MA", "outcome": "Motion Adopted"},
    "first_seen": "2027-01-07T15:42:58Z", "note": null}],
 "tallies": [
   {"body": "S", "bill": "2027-2028/SB12", "line": "Ought to Pass, RC 15Y-8N, MA; 01/07/2027",
    "yeas": 15, "nays": 8, "outcome": "Motion Adopted",
    "first_seen": "2027-01-07T14:21:03Z", "rollcall": null}],
 "notes": {"record": "The night's record replaces this file each morning; a roll call the record holds wins.",
           "excusals": "Excused and not excused settle in the days after a vote.",
           "senate": "Senate names follow once the Senate enters them, usually that afternoon or the next day.",
           "reading": "read_at and next_read_by describe this reader alone, and say nothing about any stream."}}
```

**Fields:**
- **Ids** are `plan.md` §4.3's v1 ids. The term comes from the session year: an odd year starts its term.
- **`taken`** is the House's `VoteDate`, converted from New Hampshire time. For the Senate it is `null`, because its `VoteDate` is midnight, and `saved` carries `DateModified`.
- **`keyed_by`** is `"voting system"` for `VOTE SYSTEM`, otherwise `"clerk"`. Raw user names are not published.
- **`first_seen`** against `taken` is the freshness measurement itself, on every House roll call, against the voting system's own stamp, which this project did not generate. A laptop script summarises it from the files within 30 days. There is no separate "January measurement".
- **`notes.reading` documents plainly** that the cadence fields describe the reader alone (safe review, low).

**Headers (set by the Function):**
- `Content-Type: application/json; charset=utf-8`;
- `Access-Control-Allow-Origin: *`, with `Access-Control-Expose-Headers: ETag`, and an `OPTIONS` preflight answered 204 (`GET, HEAD`; `If-None-Match`), so a page elsewhere can poll with `If-None-Match` as the docs ask (added 30 October 2026, the Functions' review);
- `X-Content-Type-Options: nosniff` on every answer;
- `Cache-Control: public, max-age=15`, with a 15-second copy per data centre through the Cache API;
- `ETag` from R2's `httpEtag`, and `304` on `If-None-Match`;
- `404` with `max-age=60` for a date with no file;
- `404` everywhere without the binding;
- `GET`/`HEAD` only; anything else gets `405`.

**Not public: `GET /api/live/streams`.** It is Live Now's own data and is not documented. YouTube developer policy III.I.15 forbids offering an API service that gives access to YouTube API data (`streams.md`'s reading, not legal advice). It is sent with **no CORS header**, `X-Robots-Tag: noindex` and `Cache-Control: public, max-age=30` (30 rather than 15 since §1.6, so that /live and every committee page poll one cached answer). It serves today's `streams/` file, or yesterday's in the minutes after midnight before today's exists. A test holds that it never sends `Access-Control-Allow-Origin` (safe review, low).

**The docs ask clients** to poll at most every 30 seconds with `If-None-Match`, and to treat the record as the truth. Nothing a client does reaches the General Court or YouTube.

---

## 6. Every new running piece, secret and setting

### 6.1 Pieces

| Piece | What it asks, how often | Costs | When it is down |
|---|---|---|---|
| **Worker `graniterecord-live`** (`workers/live/`): cron `*/2 * * * *`, `workers_dev = false`, no route. Deployed by a person with `npx wrangler deploy --config workers/live/wrangler.toml --env production` | **YouTube Data API:** ≈ 1,270 units and 52 searches a weekday (§1.1). **PublicSQL**, TCP 1433, SELECT only: while a chamber sits, and a heartbeat on weekdays January–June; ≤ 1,200 statements a day; 846 on the heaviest day of 2025–26 (§2.3). **Never gc.nh.gov. Never graniterecord.org** | 720 runs a day on Workers Paid, already paid ($5/month); milliseconds of CPU a run. **≈ $0 extra** | Pages show today's schedule and "not checked since …" or "Not read since …", with the record arriving in the morning. Healthchecks emails |
| **R2 bucket `graniterecord-live`**, private (`npx wrangler r2 bucket create graniterecord-live`) | nobody | ≈ 70 k Class A and < 1 M Class B a month: **$0** | the Functions answer 503; pages fall back to their static content |
| **Pages Functions** `functions/api/live/streams.js` and `functions/api/live/votes/[day].js` (with `functions/api/live/_store.js`), deployed with every Pages publish | nobody; they read the bucket only | Function calls within the 10 M included (guess: about 1–2 M a month at a session peak) | as for the bucket |

### 6.2 Configuration: where the real host may and may not appear

**This answers the safe review's high finding, that local or test runs could reach the real SQL host.**

```toml
# workers/live/wrangler.toml
# Top level: only what `wrangler dev` runs, against a fake TDS server on this machine.
# Never deployed: it has no cron, no secrets, and its host is the loopback address.
name = "graniterecord-live-local"
main = "index.js"
compatibility_date = "2026-09-04"
workers_dev = false
[vars]
SQL_HOST = "127.0.0.1"
SQL_PORT = "24817"
[[r2_buckets]]
binding = "LIVE"
bucket_name = "graniterecord-live-local"
[observability]
enabled = true

# Production: the only place the General Court's host is named outside probe_db.py.
[env.production]
name = "graniterecord-live"
workers_dev = false
[env.production.triggers]
crons = ["*/2 * * * *"]
[env.production.vars]
ENV = "production"
SQL_HOST = "<probe_db.HOST>"   # written here only as probe_db.HOST; preflight holds them equal
SQL_PORT = "1433"
[[env.production.r2_buckets]]
binding = "LIVE"
bucket_name = "graniterecord-live"
```

**Read** (Cloudflare's Wrangler configuration page, updated 20 October 2026):
- `triggers` and `workers_dev` are inheritable;
- `vars` and bindings are not, and "need to be defined explicitly".

So the cron exists only in production, and top-level `vars` never reach production or the reverse.

**Three layers keep a local run or a test off the real host:**
1. **The configuration above.** The top level names only `127.0.0.1`. `ENV = "production"` exists only under `[env.production.vars]`.
2. **The client's loopback guard** (§2.1). It refuses any non-loopback host without `ENV = "production"`, even if someone edits the top-level host.
3. **Preflight:**
   - the host (`probe_db.HOST`) appears nowhere in `workers/live/*.js`, `functions/api/live/` or `tests/live/`, and only on the one production line of `wrangler.toml`;
   - that line equals `probe_db.HOST`;
   - the top-level `[vars]` names only loopback;
   - the README's deploy line carries `--env production`.

**`.claude/hooks/guard.py` gains two entries** (a project file, proposed with branch 2; the person approves it with the branch):
- `wrangler dev` with `--config workers/live` and `--env production` (or `--remote`) is **denied**, with the General Court reason;
- `wrangler r2 object put graniterecord-live/control.json` **asks**, with the reason "this turns the live layer's reads of the General Court's database on or off".

**`workers/live/live.gen.js`** is written by `src/pages/live_gen.py` from the sources, never copied by hand. This is the `workers/follow/site.gen.js` pattern: preflight fails while the file differs from what its generator would write. It carries:
- `probe_db`'s `DATABASE`, `USER` and `PASSWORD`, published by the General Court and not secret. **The host is deliberately not in it.** The generator reads them by parsing `probe_db.py`, importing no fetcher;
- `fetch_rollcalls_db.VOTE_WORD`;
- `fetch_channel_index.CHANNELS`;
- `refusal.NIGHT_WINDOWS`;
- the outcome abbreviations from `records/docket_abbrev.json`;
- the session-title pattern.

The Worker imports `nhClock` from `workers/follow/common.js` rather than copying it.

### 6.3 Secrets and switches

| Name | Where | What |
|---|---|---|
| `YOUTUBE_API_KEY` | `npx wrangler secret put YOUTUBE_API_KEY --config workers/live/wrangler.toml --env production` | A **second key in the existing Google project** (policy III.D: one project per API client), restricted to "YouTube Data API v3". A Worker has no fixed address, so there is no IP restriction |
| `HEALTHCHECK_URL` | the same way | A new Healthchecks check: 2-minute period, 10-minute grace |
| `control.json` | the bucket, by a person, `--remote` | **the one switch** (§2.6). Missing means shadow |

**There is no other secret,** no GitHub or Cloudflare token, and no `wrangler.toml` switch.

### 6.4 The site's binding, and previews

**The root `wrangler.toml`** gains `[[env.production.r2_buckets]]` and `[[env.preview.r2_buckets]]`, both binding `LIVE` to `graniterecord-live`, and a top-level one to a local name for `wrangler pages dev`.

**Previews read the production bucket, accepted explicitly.** The root `wrangler.toml` gives previews their own stores so that a test report never lands among real ones (safe review, low). That rule exists because those Functions *write*. These only read, and a preview that can show the real day's live data is how the page is tried on real data before launch. The write risk is closed three ways:
1. `_store.js` is the only line that names `env.LIVE`, and it exposes `get` and `head` alone.
2. Preflight fails if `functions/api/live/` calls `put`, `delete`, `list`, `createMultipartUpload` or `resumeMultipartUpload`, or names `env.LIVE` outside `_store.js`.
3. Every dry run runs `preflight.py --code` before it fetches, builds or deploys anything (read, `nightly.py`), so a branch whose Function writes is never deployed.

The alternative, a `graniterecord-live-preview` bucket a person copies into, is named in §10 (default 4).

**The binding lands only after the bucket exists** (simple review, low). It is proved on a dev dry-run preview deploy before it reaches `main`. Whether the nightly's Pages token needs R2 permission to deploy a binding is not known (§10). If it does, widening that token is one named step for the person.

### 6.5 CLAUDE.md's paragraph, for the owner to place once approved

> Live Now and live session votes add one more, approved by the person on [date]: `workers/live/`, a Worker with no address whose cron, every two minutes, asks YouTube's Data API which House and Senate streams are live, and — while a chamber sits, plus one small query every fifteen minutes on weekdays from January to June — asks the General Court's public SQL database (never gc.nh.gov) for the day's roll calls, ballots and docket tally lines, at most 1,200 statements a day, keeping out of the night's window unless a session stream is live. It writes to one private R2 bucket, `graniterecord-live`; `control.json` there, written only by a person and always with `--remote`, is the switch, and stops the database half or the whole Worker at its next run. `functions/api/live/` reads that bucket and nothing else. No page waits on them: `/live` and the session pages are drawn by the night and say when live data was last read, never "nothing is live"; the night's record replaces the live copy every morning. The stream list is the page's own data and is deleted after 30 days (YouTube's developer policy III.I.15 and III.E.4.d); the live votes file is public and provisional.

`_follow_documents_live` already fails until `SECURITY.md` names `workers/live/` and `functions/api/live/` (read). A's further check, failing until CLAUDE.md names them, is not added (simple review).

---

## 7. The checks, and trying it before a sitting

### 7.1 What preflight holds (fakes only, no network)

**One node suite, `tests/live/`,** is run by one preflight check exactly as `_night_timer` runs `tests/night-timer.test.js`: `node --test`, TAP, and a minimum count. Its files:
- **`clock.test.js`:**
  - the four states of §2.3 and every YouTube cadence across 14 March and 7 November 2027;
  - `NIGHT_WINDOWS` honoured, with the one exception;
  - the heartbeat's hours and season, and its 14 days after a sitting;
  - nothing due on a quiet weekend.
- **`youtube.test.js`.** A fetch that is a function, with **synthetic** answers in the documented shape: recorded answers would be API data kept in git indefinitely (III.E.4.d; safe and simple reviews, low on B). It covers:
  - status classification, with preflight running `livestreams.status_of` on the same synthetic answers;
  - `maxResults=50`;
  - upcoming ids kept across days and dropped after 30;
  - quota per simulated weekday ≤ 1,300 units and ≤ 52 searches;
  - `quotaExceeded` held to midnight Pacific;
  - five failures turning into `/fail`.
- **`tds.test.js`.** The client against `tests/live/fake_tds.js`, started in-process on port 0:
  - an ordinary read;
  - a reply over many 4,096-byte packets, with `NBCROW`;
  - two statements on one connection;
  - `ENCRYPT_REQ` → `encrypt`, **with no LOGIN7 sent**;
  - `Login failed` → `login`, and 4060 told apart;
  - an `ERROR` token → `query`;
  - **a fixed-length INT4 column → `type`**;
  - `LOGINACK` older than 7.2 → refused;
  - a silent server and an unconnectable address each fail inside the deadline;
  - LOGIN7 decoded field by field, with application and host names;
  - **a non-loopback host refused without `ENV = "production"`.**
- **`votes.test.js`:** the replays (§7.2), plus:
  - the merge (never drop, the note after three misses, `first_seen` never moves);
  - the docket parse (`RC` before digits only);
  - a Senate tally attached when its roll call arrives;
  - every hold and its expiry;
  - the budget;
  - `control.json` honoured, missing and unreadable;
  - every SQL string built only from integers and `'YYYYMMDD'` dates.
- **`store.test.js`** (an R2 fake with etags):
  - the lease;
  - an overlapping run writes nothing;
  - a public file is never written without the lease;
  - a lost `state.json` is harmless;
  - **a run with something due that writes nothing fails the test.**
- **`functions.test.js`:**
  - 404 without `LIVE`;
  - GET/HEAD only;
  - only the two path shapes, so `control.json`, `state.json` and `test/` are unreachable;
  - CORS on votes only; `noindex` on streams;
  - 304;
  - the today-or-yesterday streams rule.
- **`page.test.js`.** `live.js` under `dom_stub.js`, as preflight loads `app.js`:
  - "stale" is said as stale against `next_check` and `next_read_by`, and a quiet weekend is not stale;
  - the strings "not streaming" and "nothing is live" never appear;
  - every `status.problem` code gets its own sentence, and an unknown one gets "Not read since …";
  - the union by id (the record wins, and a late Senate save shows on a past page);
  - a refresh keeps an opened player's iframe;
  - the today page shows the previous day before 06:00.

**Python checks** go in one preflight function, `_live_layer`, beside `_night_timer`. They move with the rest if `plan.md` §5 item 8 creates `src/checks/suite/` first. It holds:
- `live.gen.js` equal to its generator's output;
- the host rules of §6.2;
- `workers_dev = false` at both levels, the cron only under production, no `routes`, and the production name;
- **every SQL statement in `workers/live/sql.js`** is one SELECT over the four views, with no comment, no `;` and no `*`; every output column a `CAST(… AS nvarchar(n ≤ 4000))` or `CONVERT(nvarchar(19), …, 126)`; and literals only from the one builder. This reuses `fetch_past_db.select_only`'s refused list;
- no `gc.nh.gov`, `gencourt` or follow database name in `workers/live/` or `functions/api/live/`;
- the Functions' read-only rule (§6.4);
- every `wrangler r2 object` line in `workers/live/README.md` carrying `--remote`, and every file in `workers/live/control/` parsing to allowed values;
- the JS title stem equal to the Python stem on every title in `collected/videos/`, and the session pattern matching the 172 session titles and no other;
- `schema/session.votes.json` validating the night's per-day file on the fixture build and the replay's live file.

### 7.2 The replays (files in git only, so they run in a cloud session too)

The fake server releases each row at its recorded time plus a set lag. The Worker runs on a fake clock from 07:00 to 23:59, with the real cadence rules (works review, high: B's replay ran its clock to 21:00 and never tested its own cap).

| Replay | From | Asserts |
|---|---|---|
| **11 March 2026, House** | 56 roll calls to 20:46; the session stream 08:58–20:49 (`collected/videos`) | every roll call in the file within two runs of its release; final tallies and every ballot equal to `RollCallHistory_2026.txt`; 395 connections and 846 statements (± a few), under the budget; nothing read after the tail |
| **12 March 2020, House, with no stream** (none was recorded) | 49 roll calls to 23:58 | the heartbeat, which starts at 09:30 EDT, finds the first roll call (09:53) at its 10:00 run; hot follows the roll calls; a gap over 45 minutes falls to warm and comes back; every roll call is in the file within 15 minutes of its release. **Votes without YouTube** |
| **29–30 January 2026, Senate** | rows released at their recorded `DateModified`, S 9 and S 11 the next morning after S 10 and S 12 | every roll call reaches `votes/2026-01-29.json`, the out-of-order two through the next morning's wide read |
| **A docket day** | synthetic lines in the recorded forms: House "MA RC 190-171" created 4.4 minutes after the vote; Senate "Ought to Pass, RC 16Y-8N, MA; 01/29/2026" created ten days ahead and filled in during the sitting | Q3's filter takes both; tallies attach |

### 7.3 Measured before relying (no network; on the laptop with the kit)

From the kit's `Docket.txt` (2025–26):
- the share of Senate `RC nY-nN` lines carrying their sitting's date as `MM/DD/YYYY`;
- the share of House `RC n-n` lines created on the sitting day.

If either is under about 95%, Q3's text test is widened: lines entered in the last 21 days, filtered in JavaScript. This runs in branch 3, before the November test's Q3 comparison.

### 7.4 The calendar of trying

| When | What | Asks |
|---|---|---|
| Any time | the suite and the replays | nobody |
| Any time, on the laptop | `wrangler dev --config workers/live/wrangler.toml --test-scheduled` against `fake_tds.js` on 127.0.0.1; `/__scheduled` with `LIVE_CLOCK` set | nobody (the host is loopback by configuration and by the client's guard) |
| ≈ 13 November, after D1 | the person creates the bucket, the key and the check, and deploys. No `control.json`, so shadow: YouTube only. `seen` is read with `wrangler r2 object get … --remote` | YouTube |
| 16–18 November | the pre-scheduled House budget hearings: matching, players and the kept upcoming ids, on real streams; unscheduled House streams through November | YouTube |
| ≈ 18–24 November | `control.json` = `sql-test` (§2.7); the comparison; go or no-go | PublicSQL, ≈ 22 connections in all |
| 1 December | `control.json` = `on` | — |
| 2 December, Organization Day | the whole sitting path on real streams; the votes file must end with no roll calls; the Senate's first live test of discovery | YouTube; PublicSQL ≈ 200 statements (guess, from a 2-hour sitting and its tail) |
| ≈ 9 December | the page branches merge and release: **Live Now public** | — |
| The first session day | votes provisional and public; `first_seen` against `taken` read that evening | as §2.3 |

---

## 8. Build order

These are small branches off `dev`, each landing something that runs (simple review: the YouTube shadow must not wait behind the votes work). Sizes are agent-days and guesses: **S** about half a day, **M** one to two, **L** three to five. Branches 5 and 6 touch the night's build. So they are built and tried on their own branches' dry-run previews (any branch's run by hand is a dry run, deployed to `dry-run.graniterecord.pages.dev`), and land after `plan.md` §7's 6 December freeze.

| # | Branch | What | Size | When |
|---|---|---|---|---|
| 1 | `live/youtube` | `workers/live/` (`index.js` run planner, `clock.js`, `youtube.js`, `store.js` lease and retention, `wrangler.toml`, `README.md`, `control/`), `live.gen.js` and its generator (channels, title pattern, windows), `tests/live/{clock,youtube,store}.test.js`, `_live_layer` (first half), the `SECURITY.md` lines | M | by 12 Nov; **deployed in shadow by the person after D1** |
| 2 | `live/tds` | `tds.js`, `sql.js` (Q1–Q3 builders and the shape check), test mode and `compare_test.mjs`, `fake_tds.js`, `tds.test.js`, the SQL constants into `live.gen.js`, the guard.py entries | M | by 17 Nov, then the test |
| 3 | `live/votes` | `votes.js`: the states, heartbeat, windows, budget, merge, docket parse, holds, control; the replays; the §7.3 measurement | M–L | by 28 Nov, so `on` from 1 Dec |
| 4 | `live/functions` | the two Functions, `_store.js`, the root `wrangler.toml` bindings, `functions.test.js`; proved on a dev dry-run preview once the bucket exists | S | late Nov |
| 5 | `live/page` | `live/schedule.json` from `build_calendar.py`; `/live`; `live.js` (streams and the session card); the home line; `find.json`; Spanish strings; `page.test.js`; the stem and stale checks; `home.json`'s `status["live"]` removed | M–L | built in Nov; lands after 6 Dec; **public ≈ 9 Dec** |
| 6 | `live/session` | the night's `session/<B>/<date>.json` in the shared shape (stage 1, P9) and `prune`'s care of it; `schema/session.votes.json`; `/session/<B>/today`; the overlay hook; the union-by-id test | M | 7–20 Dec |
| 7 | `live/docs` | the `/developers` section for the live votes file and its manifest entry; READMEs; the courtesy rule in `watchers/README.md`; CLAUDE.md's paragraph handed to the owner | S | by 30 Dec |
| (8) | `live/github-poller` | **only on a no-go** (§2.8) | M | Dec |

**In all, about 2,000 lines of code and 2,000 of tests (guess), or 8–11 agent-days.** The person's part is about half an hour of setup, two `control.json` changes and reading the test files once.

---

## 9. What this keeps out

| Was proposed | Here | Why it is safe to leave out |
|---|---|---|
| A Windows GitHub job for votes, a GitHub token in a Worker, a Cloudflare token in GitHub (`plan.md` stage 3, D28) | none, unless §2.8 | the Worker speaks TDS itself |
| A new weekday 08:00–20:00 `NIGHT_WINDOWS` entry and a laptop stand-down (`plan.md`) | none | the Worker honours the existing windows; the IT office allows concurrent reads of PublicSQL; the laptop's courtesy is a default (§10) |
| The evening run (D9), the export poller, the January measurement step | none | daytime reads are allowed, and `first_seen` measures every roll call |
| KV, merged by one read address | one R2 bucket, two files split by source, no Function merges | strong consistency; the public file cannot carry YouTube data |
| A's forecast shells from `LSRs.txt` floor dates | none | `/session/<B>/today` needs no forecast and publishes no sitting |
| A's `live/people.json` | none | `/legislators.json` already exists, with corrections |
| A's Worker read of `/data/manifest.json` and `superseded_by` | none | union by id in the page |
| A's `MODE`/`VOTES` and B's `LIVE_SQL` vars, B's person-written `hold/sql.json` | `control.json` | one switch, one writer, no deploy |
| A's appended `log/*.jsonl`; `plan.md`'s 120-day shadow keys | none | measurements live in the day files for 30 days; codes go to Workers Logs |
| B's sequence cursor | none | re-reading a window whole is robust to edits, re-keys and late saves, and has nothing to lose |
| A's date-gated and CLAUDE.md-gated checks | none | the page goes public by a merge to `main`, which is already the person's decision |
| B's 20:00 end; B's `StatusDate` Senate filter; B's 10-item playlist and Senate-only search | replaced | §2.3, §2.2, §1.1 |

**New in kind:** a TDS client of about 250 lines that this project owns. It is limited to one column type and three fixed statements, tested against a fake that a real driver agrees with, bounded at every step, and fails closed where `tedious` in workerd failed open.

---

## 10. Unproven, and the owner's decisions

### Unproven, with how each gets answered

| What | Answered by |
|---|---|
| PublicSQL does not force encryption (otherwise a Worker cannot read it) | §2.7, the first connection's PRELOGIN answer |
| PublicSQL accepts Cloudflare's addresses on 1433 | the same, and the daily login over the following weeks |
| The client against a real SQL Server (only fakes, and tedious, have answered it) | §2.7 day 1; tedious, which ran unencrypted in workerd, is the drop-in if needed |
| `CONVERT(…, 126)` and the nvarchar casts accepted by this server | §2.7, compared with the record |
| Q2 and Q3 cost on the host (`RollCallHistory` 2.3 M rows; `Docket` 317,811 rows over two databases; indexes unknown) | §2.7 records each statement's time; Q3 over 1 s falls to one hot run in five |
| Senate `RC` lines carry the sitting's date in their text | §7.3, on the kit's `Docket.txt` |
| How soon a roll call reaches PublicSQL during a sitting ("updates immediately", the IT office) | `first_seen` against `taken` on the first House sitting |
| The uploads list carries an unscheduled stream while it is live | November shadow and 2 December; search stays on until then, per channel |
| A morning-of agenda for House sittings | a follow-up: the calendars' session notices (`legislative_year.py` already cites them, for example "The House will meet on Wednesday, January 7, 2026") and their bills. Until then, the Calendar's floor card when it has one |
| `/legislators.json` holds the 2027 House before 6 January (after the 2 December term turn) | the night of the turn; otherwise ballots show as "not yet on this site's roster", counted, never dropped |
| Whether the nightly's Pages token can deploy an R2 binding | branch 4's dry-run preview deploy |
| How often Cloudflare fires a cron twice | the lease makes it harmless; the Healthchecks ping body shows the runs |
| GitHub refuses a dispatch carrying an undeclared input (422) | only matters for §2.8; tested on that branch |
| The cost and traffic figures | guesses, labelled so; the Cloudflare dashboard after a month |

### The one decision

**D1, widened.** Approve the Worker `graniterecord-live`, its private R2 bucket and its two read-only addresses. That includes reading the General Court's public SQL database while a chamber sits, a 15-minute heartbeat on weekdays from January to June, at most 1,200 statements a day, and never gc.nh.gov. Approve also the two keys the person creates.

### Defaults that come with it, each changeable later

1. **Votes public from the first session day,** provisional, with both times on each card. The live votes file goes in API v1 as beta, and the streams file never.
2. **The night's window:** the Worker stays out of it except for a chamber whose session stream is live. In that case it and the night may query PublicSQL at once, on the IT office's word.
3. **A courtesy note to the IT office** before the November test: one connection every 2 minutes while a chamber sits, about 450 statements on a typical sitting day and at most 1,200, SELECT only, from Cloudflare's addresses.
4. **Previews read the production bucket,** behind the read-only facade (§6.4). The alternative is a preview bucket the person copies into.
5. **The laptop:** a courtesy rule in `watchers/README.md`: no whole-table `fetch_*_db` pull on weekdays 09:00–18:00 from January to June. It is not enforced. The alternative, extending `refusal.window_check` to those hours, would stop the laptop's database pulls by day for half the year.
6. **A no-go in November** brings §2.8 back as its own decision, with its three secrets.

---

## 11. Every review problem, and where it is answered

| Review | Design | Severity | Problem | Answer |
|---|---|---|---|---|
| works | B | high | Reading stops at 20:00; 7 of 11 March 2026's 56 roll calls came after it | No clock cap: hot while the stream is live or roll calls keep coming; 5-hour warm tail to 23:59 (§2.3). Replays of 11 March 2026 and 12 March 2020 under the real rules (§7.2) |
| works, safe, simple | B | medium | Q3 by `StatusDate` misses Senate lines entered ahead | One filter: entered today, or entered in the last 21 days with today's date in the text (§2.2), measured first (§7.3) |
| works, safe | B | medium | Pre-scheduled House streams missed; `maxResults=10`; no House backstop; no upcoming ids kept | `maxResults=50`; upcoming ids kept ≤ 30 days and re-asked daily; search on both channels (§1.1) |
| works, safe, simple | A | medium | Votes depend on YouTube; trigger (c) needs `schedule.json`, which the Worker said it never reads | The heartbeat (§2.3); the Worker reads nothing from the site; the 2020 replay runs with no stream |
| works | A | low | Fixed-length TDS types rejected | Everything cast to nvarchar; the client takes one type and fails closed on others, tested (§2.1, §7.1) |
| works | B | low | The cursor skips out-of-order Senate saves; a lost cursor reads the whole year | No cursor; a 14-day wide read; nothing to rebuild (§2.2, §3.2) |
| works | A | low | Senate saves on a later day never reach the live file | The wide read, filed under `VoteDate` (§2.2, §2.4) |
| works | both | low | `_columns.json` has no types; DMY literals; R2 has no append; Q3 untimed | Casts need no types; `'YYYYMMDD'`; no log object; Q3 timed in §2.7 |
| safe | both | high | A local or test run could reach the real host | The host only under `[env.production.vars]`; loopback guard; preflight; guard.py entries (§6.2) |
| safe | B | high | The stop without `--remote` writes local storage | `control.json` with `--remote` everywhere, held by preflight; the Worker reports what it honours (§2.6) |
| safe | both | medium | The one-at-a-time rule misread; the night window overlapped; laptop concurrency | The Worker honours `NIGHT_WINDOWS` with one stated exception; the rule cited correctly; the laptop a named default (§2.3, §10) |
| safe | A | medium | No runtime budget | 600 connections, 1,200 statements or 150,000 rows a day, held and reported (§2.3) |
| safe, simple | A | medium | Forecast shell pages for sittings that may not happen | None; `/session/<B>/today` publishes no sitting (§4.2) |
| safe | both | medium | "Not streaming" and "nothing is streaming" state a negative discovery cannot prove | "No stream found … (checked …)" (§1.4) |
| safe | B | medium | One failure sentence blames the General Court for the Worker's own stops | A sentence for each code; "Not read since …" when overdue (§2.6) |
| safe | both | medium | Fallbacks put the power to start the night in a new place | `night-timer` untouched; dispatch only `live-votes.yml`, held by preflight; the 422 guard; the dry-run defaults (§2.8) |
| simple | B | high | No session-day page for a House sitting on its own day | `/session/H/today` and `/session/S/today` (§4.2) |
| simple | A | medium | The Worker reads the manifest to supersede; two mechanisms for one rule | Union by id in the page; the Worker never reads the site (§4.3–4.4) |
| simple | A | medium | Compare-and-set guards the wrong object; state duplicates the votes file | A lease before any write; public files only under it; state holds no votes (§3.2–3.3) |
| simple | A | medium | New night machinery on an unmeasured forecast; a second roster file | No forecast; `/legislators.json` (§4.2, §2.5) |
| simple | A | medium | The off switch cannot reach night-written pages; date- and document-gated checks | `control.json` for what runs; going public is a merge to `main`; no gated checks (§2.6, §9) |
| simple | B | medium | The YouTube shadow waits behind the votes branches | A YouTube-only branch first, deployed in shadow (§8) |
| simple | B | medium | Two writers on `hold/sql.json`; two switches | The person writes `control.json` alone; the Worker's holds live in `state.json` (§2.6, §3.2) |
| simple | B | medium | A rejected login held until a person clears it | It expires with the day and lifts at once on changed credentials, as `probe_db` (§2.6) |
| safe, simple | B | low | Recorded YouTube fixtures kept in git | Synthetic answers, held to the Python on the same (§7.1) |
| safe | both | low | Stream data open cross-origin | CORS on votes only; streams with none, `noindex`, tested (§5) |
| safe | both | low | Previews bound to production with a write binding | Accepted explicitly behind a read-only facade; preflight runs before any deploy; the alternative named (§6.4) |
| safe | A | low | The public file written before the state compare-and-set; two SQL connections possible | The lease (§3.3) |
| safe | A | low | "No roll calls yet" claims something about the chamber | "No roll calls read yet today (read at …)", plus the Senate line (§2.6) |
| safe | A | low | The login test re-reads the same past sitting daily | Each past sitting is read once; later days only log in (§2.7) |
| safe | both | low | The public file's cadence hints at stream status | `notes.reading` says the fields describe the reader alone (§5) |
| simple | A | low | The binding before the bucket exists | Branch 4 after the bucket, proved on a dry-run preview (§6.4) |
| simple | B | low | The heartbeat inside the night's window, said not to be | It starts at the window's end, 08:30 EST or 09:30 EDT (§2.3) |
| simple | B | low | Fallback detail (`night-timer`, every weekday, R2 secrets miscounted) | Started from the live Worker when a chamber is hot; both R2 secrets named (§2.8) |

---

## Sources

**Cloudflare:**
- Wrangler configuration, updated 20 October 2026, read today: `triggers` and `workers_dev` are inheritable; "Bindings, such as `vars` … are not inheritable and need to be defined explicitly". https://developers.cloudflare.com/workers/wrangler/configuration/
- TCP sockets, updated 13 October 2026 (re-read by the works review): sockets in `scheduled()`, the blocked ranges, and `startTls()` only on a `starttls` socket. https://developers.cloudflare.com/workers/runtime-apis/tcp-sockets/
- Workers limits, updated 12 October 2026: 30 s of CPU for a cron under an hour, 15 minutes of wall time, six connections. https://developers.cloudflare.com/workers/platform/limits/
- R2 consistency, updated 14 October 2026. https://developers.cloudflare.com/r2/reference/consistency/
- R2 Workers API, updated 31 July 2026: `put` returns `null` on a failed `onlyIf`. https://developers.cloudflare.com/r2/api/workers/workers-api-reference/
- How KV works, updated 21 April 2026. https://developers.cloudflare.com/kv/concepts/how-kv-works/
- Cron triggers, updated 17 October 2026. https://developers.cloudflare.com/workers/configuration/cron-triggers/
- Pages Functions bindings, updated 25 June 2026: R2 bindings from the Wrangler file. https://developers.cloudflare.com/pages/functions/bindings/

**GitHub:**
- Actions limits: "Each job in a workflow can run for up to 6 hours"; 35 days a workflow run. https://docs.github.com/en/actions/reference/limits
- Actions billing: free for public repositories on standard hosted runners. https://docs.github.com/en/billing/concepts/product-billing/github-actions
- The repository is public: `gh api` → `"visibility": "public"` (measured by A, B and two reviews).
- A dispatch with an undeclared input is refused with 422 (third-party reports, not GitHub's docs):
  - [a pull request whose dispatch failed this way](https://ithub.global.ssl.fastly.net/THEROER/MagicUtils/pull/30)
  - [Qameta support's note on the 422](https://help.qameta.io/support/solutions/articles/101000484310-error-422-when-trying-to-trigger-github-workflows-from-allure-testops)
  - [Graphite's guide to `workflow_dispatch` inputs](https://graphite.com/guides/github-actions-workflow-dispatch)

**Microsoft:** MS-TDS 2.2.6.5 PRELOGIN encryption negotiation. https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-tds/60f56408-0188-4cd5-8b90-25c6f2423868

**YouTube:** the quota (search's own allowance of 100 since 1 June 2026; 10,000 units otherwise; reset at midnight Pacific), the `videos.list` fields, and the policy readings III.D, III.E.4.d and III.I.15. All are as cited in `/tmp/claude-0/audit/wf15/streams.md` §2, and the quota page was re-read by the works review (15 October 2026).

**Experiments relied on:**
- `/tmp/claude-0/audit/wf16/A/exp/` (the client, the fakes, tedious, workerd);
- `/tmp/claude-0/audit/wf16/B/exp/` (the minimal client with the connect deadline, tedious failing open with encryption, the 11 March 2026 replay);
- `/tmp/claude-0/audit/wf16/R3/scripts/` (the save order and late votes);
- `/tmp/claude-0/audit/wf16/final/scripts/` (`days.py` and `load.py`, this design's load figures).
