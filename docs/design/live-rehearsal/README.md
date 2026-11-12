# Live Now, rehearsed: the screenshots

Each state of Live Now that `src/pages/build_live_rehearsal.py` writes at
`/live/rehearse/<state>` (branch `live/rehearsal`, which never merges), at
390 and 1280 wide, light and dark: `<state>-<width>-<scheme>.png`.

**Taken on the committed fixture site, not on a dry run.** What is real and
what is not:

| Part | Here | On a dry run's preview |
|---|---|---|
| Roll calls (number, bill, question, tally, time) | real: `records/rollcalls/RollCallSummary_2026.txt` | the same |
| Streams (title, start, end) | real: `collected/videos/` | the same |
| The docket's outcome on a roll call | the fixture's `data/rollcalls.csv`, which holds few of these days' votes, so most read "outcome not yet in the docket" | the built record's, for every vote |
| The calendar (/live's cards, the day's agenda) | the fixture's, which has no 19 August: no floor row, so no session card on /live and every bill on the day page "not on the day's calendar" | the real calendar |

So these show the pages working state by state. The dry run is where the
cards and outcomes are real.

| State | What |
|---|---|
| a | Nothing live, the next sitting ahead (18 August 2026, 18:00 ET) |
| b | Committees streaming, matched to their agenda (10 March 2026, 10:00 ET) |
| c | The House sitting: /live (19 August 2026, 11:50 ET) |
| c-day | The House sitting: its day's page, vetoes overridden and sustained |
| d | Both chambers sitting (14:00 ET) |
| d-senate | The Senate's day, its roll calls saved after it rose (16:00 ET) |
| e | The day over, before the night's record (19:30 ET) |
| f | The morning after: the record's own page, `/session/H/2026-08-19` (not shot here: the fixture has no such page) |
| g-youtube | YouTube off |
| g-stale | Live status stale (the last look 40 minutes old) |
| g-votes-off | The database half off |
