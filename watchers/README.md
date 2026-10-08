# The long-running loops

These four ran for days out of a session scratchpad — a temp directory keyed to
one conversation — which meant that when the conversation ended they kept
running and nobody could find them again. On 10 September one of them, a wait
loop, polled every fifteen seconds for eleven hours and forty minutes for a
success token that a crashed build was never going to write. It reported
nothing the whole time, because it had a success path and no failure path.

So they live here now. They are not part of `build_all.py` and nothing calls
them; they are started by hand, they run until stopped, and this page is how
the next person finds out what is already running before starting a second
copy of it.

What is left here is the lane, `gc_lane.py`, its queue and the pause it can
run as a step (`rest.py`). The other loops finished their work and moved to
`obsolete/` -- `docket_chain.py` on 1 October 2026, and `captions_watch.py`,
`extract_watch.py` and `narrative_watch.py` on 6 October -- where
`obsolete/README.md` says what each was and why it is kept.

**Check before you start one.** Two of the same watcher is two fetchers.
Pasted into `cmd` as it stands, this lists every watcher, the lane, a
nightly, any fetch or probe, `resolve_members`, the snapshot, a publish and a
`cloud.py` transfer, each with its command line:

```
powershell -NoProfile -Command "Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'gc_lane|nightly|fetch_|probe_|resolve_members|snapshot_gencourt|publish|_watch\.py|cloud\.py' } | Select ProcessId,CommandLine | Format-List"
```

With nothing running it lists one process: itself. The one it replaces wrapped
the same PowerShell in `python3 -c` with `\"` inside double quotes. `cmd` has
no backslash escape, so it read that quote as the end of the string and the
`|` after it as a pipe of its own. This one quotes only with `'` inside the
`"`. It says `_watch\.py` rather than `watch`, which also matches the
`gpu-watchdog` flag of every Edge and Teams process on the machine. It names
`probe_` and `resolve_members` because they ask the General Court too. It
lists this machine only: GitHub's night is on the repository's Actions tab.

## GitHub's night, and the laptop's fetches

Since 26 September the nightly runs on GitHub, and this laptop has stood down
(`archive/runs-in-the-cloud.json`). General Court fetches still run here --
from the lane or by hand -- and the rule is still one fetch at a time, across
both machines now. On a stood-down laptop:

- **No General Court request starts in GitHub's night window, or in the half
  hour before it**: the window is 08:00 to 13:30 UTC every day (the night
  starts at 08:17 and may run four hours, and GitHub often starts it late, so
  an hour is allowed for that), and 04:00 to 06:30 UTC on Monday for the
  weekly job. In Eastern time that is 4:00 to 9:30 a.m. EDT in summer and
  3:00 to 8:30 a.m. EST in winter; on a Monday there is also midnight to 2:30
  a.m. EDT, which in winter is 11:00 p.m. EST on the Sunday to 1:30 a.m. The
  night started at 06:17 until 27 September, when it met the General Court
  rewriting its dynamicdatadump files, which it evidently does around 2 a.m.
  Eastern. `refusal.NIGHT_WINDOWS` is the one definition.
  `refusal.check()`, which every General Court fetcher calls, exits 4 inside
  it and in the 30 minutes before it, with the window in Eastern time and
  when it ends; the lane stops before its next step, daily ones included
  (exit 4, the reason in `logs/gc_lane.log`, the lock released); and a query
  of the SQL host stops in it and in the half hour before, because the night
  and the weekly query that host.
- **A run already going when the window opens stops at its next request** if
  it asks `refusal.hold().still()` before each one, as the fetchers that hold
  `archive/.lock` do -- it says the window is why, once, and a run that
  would then have ended 0 ends 4 instead, because it did not finish. Under
  the lane its hold also writes `logs/gc_lane.window-stop`, so the lane
  records that step in neither `gc_lane.done` nor `gc_lane.daily` whatever
  status it ended with, and stops with 4. A fetch that does not ask is not
  stopped, so queue a long one to start after the window closes.
- **No request starts until the bucket's refusal record has been read since
  the last window closed**, because a refusal the night meets is recorded in
  the bucket, not here. `python3 src/ops/cloud.py pull --changes-only` reads it (a
  full `python3 src/ops/cloud.py pull` does too), and brings the refusal down as
  `archive/refused.json` if the night met one -- which then stops the lane
  and every fetch here, as a refusal met here always has. Only a read of the
  real bucket counts: a pull from a `--local-bucket` folder is a test.
- **A refusal met here goes to the bucket at once** (`refusal.note()`, in the
  fetchers that record one), so the night stops too. If the bucket cannot be
  reached, or already holds an older refusal this one waits behind, the fetch
  says so loudly, and `archive/cloud/refusal-unsent.json` stays until the
  bucket holds this refusal -- `python3 src/ops/cloud.py send-refusal` sends it once
  the bucket holds none -- or a person lifts it here.

`python3 refusal.py` says whether the window is open, when the bucket was last
read, and whether a refusal is waiting to be sent. So a lane started in the
morning Eastern time starts its last step before 3:30 a.m. EDT (2:30 a.m.
EST), and a fetch still running under it stops at 4 a.m. EDT (3 a.m. EST) if
it asks `hold().still()`. On the night into a Monday both come earlier,
because the weekly's window opens at midnight EDT (11 p.m. EST on the
Sunday): the last step starts before 11:30 p.m. EDT on the Sunday (10:30 p.m.
EST), and a running fetch stops at midnight EDT (11 p.m. EST on the Sunday).
The next morning, after the window, the lane wants `python3 src/ops/cloud.py pull
--changes-only` and a restart.

---

## `gc_lane.py` -- the one worker for the General Court

Runs the General Court's fetches one after another from `gc_lane.queue`, a
line per step (what would follow `python3`), and records each finished line
in `logs/gc_lane.done` so a restarted lane picks up where it was. Lines can be
added while it runs; an empty queue is waited on for twelve hours.

The lane finds each line's script through `_paths.script`, by its bare name
in whichever code folder holds it, so a line never changes when a script
moves under `src/` -- and must not: the lane matches finished lines by their
exact text, so a rewritten line would run again.

It holds `archive/.lock` for its whole life and touches it every minute, and
the fetchers check with `refusal.hold()` that their parent is the lane that
holds it -- because several fetchers never looked at the lock, and
`fetch_calendar_archive` deletes one more than an hour old. A step marked
`handover` takes the lock itself and is given it for that step. It stops on
any step that exits non-zero, before every step if `archive/refused.json`
exists at all, and -- on a stood-down laptop -- before a step inside GitHub's
night window or the half hour before it, or before the bucket's refusal
record has been read since the last one (above). A daily step that exits 4
while `refusal.gc_turn()` says it is GitHub's turn was held, not run: it is
not recorded as run, and the lane stops. One that exits 4 when it is not
GitHub's turn is stood down for good -- the script refuses on this machine
because GitHub runs that job now -- so it is recorded as run, the log says the
line should come out of `gc_lane.queue`, and the lane goes on. A step GitHub's
window stopped part way is recorded as neither, whatever it exited (above).

```
python3 watchers/gc_lane.py            # from the repository root
tail -f logs/gc_lane.log                # the lane; each step logs to logs/gc_<time>_<step>.log
```

`rest.py SECONDS label` is a pause the lane can run as a step, so the
address sees bounded runs with an hour between them rather than one crawl.

Started 11 September with the person's leave for that absence: the
2015-2016 docket, then bill text 2017-2024 in 800-request runs. What is
queued is in `gc_lane.queue`, with the reasoning beside each line.

## Moved to `obsolete/`

- **`docket_chain.py`**, superseded by `gc_lane.py` and moved on 1 October
  2026, with `fetch_archive_text.py`, the two-request bill-text route its tail
  queued and `fetch_legislation.py` superseded on 10 September.
- **`captions_watch.py`**, the politeness loop for YouTube's captions, moved
  on 6 October 2026. Captions come through `livestreams.py` now.
- **`extract_watch.py`**, which wrote the text beside each calendar and
  journal PDF behind the calendar drain, moved on 6 October 2026. The drain is
  finished; `extract_calendar_text.py` is run by hand after a fetch of PDFs.
- **`narrative_watch.py`**, stood down on purpose after it narrated 2015-2016
  from a half-complete database seed, moved on 6 October 2026. The archived
  terms are narrated by `build_all.py` (`narrative.py`, `narrate_archive.py`).

`obsolete/README.md` says what each was and why it is kept. Nothing here
starts any of them.
