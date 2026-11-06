# Organization Day, 2 December 2026: the rehearsal

The first day the whole sitting path runs on real streams and the real
database, a week before Live Now is public (DESIGN.md 7.4). Nobody outside
sees it: the votes feed and the morning page are not linked yet. This says
what to set up, what the Worker should see, what to compare afterwards, and
what passes.

Every step that touches the bucket or the Worker is **the owner's word**:
wrangler is the owner's, and nothing here is run by an assistant. Reading the
bucket is a read (`r2 object get … --remote`) and changes nothing.

## Before the day

| When | Step | Whose word |
|---|---|---|
| By 24 Nov | The November test is done and said go (README, *The November test*; `compare_test.mjs`). Without a go, the rehearsal runs YouTube only: skip the next row. | owner's |
| 1 Dec | `control.json` = `on.json` (README, *The switch*). Healthchecks shows `on` in the next ping, within 2 minutes. | owner's |
| 1 Dec | The calendar has both chambers' floor rows for 2 Dec: `/live`'s schedule.json on the published site lists them, and Live Now shows "On today's calendar" on the 2nd. | — (read the page) |

## What the Worker should see on the day

From DESIGN.md 1.1, 2.3 and 7.4; each is a guess until the day measures it.

- **Streams.** The House and the Senate each stream their session, titled as
  in 2024: "House Session (12/02/2026)", "Senate Session (12/02/26)".
  `streams/2026-12-02.json` lists both, `live` while they sit and `ended`
  after. Other streams that day are possible but not expected (a guess:
  committees are named after Organization Day).
- **Discovery.** Each stream is first seen by the uploads playlist or by
  search within one look of its start: 2 minutes while scheduled, 30 minutes
  at worst for an unscheduled stream that only search finds (the Senate's
  first live test of discovery).
- **Chamber state.** Each chamber goes **hot** when its session stream is
  live, then **warm** for 5 hours after, then **heartbeat**. No read in the
  night's windows.
- **Roll calls: none.** No roll call has ever been taken on an Organization
  Day (DESIGN.md 600). `votes/2026-12-02.json` ends the day with an empty
  `rollcalls`, or there is no file. A roll call in it is not a failure of
  the Worker, but it must then match the record (below).
- **Budget.** About 200 statements over the day (a guess: a 2-hour sitting
  and its tail), far under the 600-connection, 1,200-statement and
  150,000-row day limits. No hold.
- **Healthchecks.** No `/fail` all day, or each one explained by its ping
  body (README, *When Healthchecks says it failed*).

## What to read afterwards (the evening of the 2nd, or the 3rd)

The owner downloads; the comparison runs offline, on the laptop or here.

```
npx.cmd wrangler r2 object get graniterecord-live/streams/2026-12-02.json --file streams-2026-12-02.json --remote
npx.cmd wrangler r2 object get graniterecord-live/votes/2026-12-02.json --file votes-2026-12-02.json --remote
npx.cmd wrangler r2 object get graniterecord-live/state.json --file state.json --remote
python3 tests/live/shadow_report.py streams-2026-12-02.json --state state.json --meetings meetings.txt
```

`meetings.txt` holds the day's two floor sittings, one a line:
`10:00 | House Session | H` and `10:00 | Senate Session | S`, at the times the
calendars give. (A votes file that is absent is a 404 from `get`: that is
the expected day, not an error.)

Compare against:

1. **YouTube's own record of the streams:** each channel's video page for the
   day, its start and end. The report prints `seen` against `started`.
2. **The calendar:** the floor rows `/live` scheduled. Each session stream
   must match its chamber's floor row.
3. **The night's record:** the next morning's session pages and
   `data/rollcalls.csv` for 2 December. Any roll call in the votes file must
   be there under the same id, with the same yeas and nays.
4. **Healthchecks:** the day's pings and their bodies.
5. **The Worker's counts in `state.json`:** statements and rows against the
   day limits.

## Pass and fail

| | Pass | Fail |
|---|---|---|
| Streams | both session streams in the day's file, each matched to its chamber's floor row | a session stream missing, or matched to anything but its floor row |
| Discovery | each first seen within 2 minutes of its start (scheduled), or 30 (search only) | later than that, or seen only after it ended |
| Votes | no roll calls, or each one in the record next morning with the same id and tally | a roll call the record does not hold, or one with a different tally |
| Reads | hot while streaming, then warm, then heartbeat; nothing in the night's windows | a read in the night's windows, or a chamber hot with no stream |
| Budget | no hold; statements well under 1,200 | a hold, or over 600 statements (three times the guess: something loops) |
| Health | no unexplained `/fail` | a `/fail` whose body does not explain itself |
| Pages | if live/session has merged: the morning pages of both chambers built the night before, noindex, with "No bills are listed for this day yet." | a morning page that says the chamber sat, or a dead link from `/live` |

A fail in **Votes**, **Reads** or **Budget** means `sql-off.json` goes back
(the owner's word) and Live Now stays YouTube-only until the cause is fixed
and tried again. A fail in **Streams** or **Discovery** is a matching or
discovery fix before 9 December: it does not touch the General Court's
server.

## What this plan cannot say yet

- Whether the calendar files carry Organization Day's floor rows ahead of the
  day (the question put to the owner on 30 October, waiting until after the
  election). If they do not, `/live` shows no floor row, and the morning page
  is not written. The streams are still found; their match is then "none".
- The statement count is a guess until the day.
