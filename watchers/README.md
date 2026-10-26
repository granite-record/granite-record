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
run as a step (`rest.py`). The other loops finished their work and were
retired -- `docket_chain.py` on 1 October 2026, and `captions_watch.py`,
`extract_watch.py` and `narrative_watch.py` on 6 October -- to an
`obsolete/` folder that was deleted on 23 October 2026. "Retired", below,
says what each was; git history keeps the code.

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

- **Once the night fetches the newest calendars and journals, this laptop
  leaves them to it.** When the night's verdict, as `cloud.py pull` brings
  it, says `NIGHT_DOCUMENTS` is a number, `fetch_calendar_archive.py`'s drain
  here leaves this year's and last year's documents that the night will
  still ask for to it, and says how many; one it will not ask for again -- a
  refusal recorded against it, three tries, no longer on its list -- the
  drain takes when a person runs it, and one the night holds back for a
  person -- a possible rename, a path two documents share, an address its
  list does not give -- only when a person names it:
  `python3 src/fetch/gc_web/fetch_calendar_archive.py --take "NAME"`. A
  drain, a `--take` or a
  `--settle` reaches the night only through the bucket: make the text
  (`python3 src/parse/extract_calendar_text.py`), then
  `python3 src/ops/cloud.py seed-kit`.
  `fetch_senate_calendars.py` stands down for those years, and
  `fetch_committee_reports.py` asks for none of those years' House
  calendars: it reads the ones on this disk instead, which
  `python3 src/ops/cloud.py docs-down` brings from the bucket. The verdict
  says a number only while the night can make the laptop's text (its text
  canary passes) and the kit gives it the texts; otherwise it says "not
  fetching", and the laptop fetches them as before -- as it does with the
  switch off or in shadow, how it landed, when the verdict does not say it
  at all. A night that ends before its canary runs, or whose pinned
  `pdftotext` does not download, keeps the night before's word.

### Turning on the night's documents

The person's steps, in order. Nothing here asks the General Court for
anything new until step 9, but a document a person names to fetch from the
laptop in step 7. The night's own notes are in `nightly.py` (THE NIGHT'S
DOCUMENTS).

Before the merge, on the laptop:

1. Check that `archive/runs-in-the-cloud.json` is there. Every rule that keeps
   the laptop and the night from asking for the same document depends on it.
2. Run `pdftotext -v`. The night pins 26.09.0; if the laptop's is another,
   say so before going on, because the release to pin is the laptop's. Then
   open `archive/extracted.json` and check that the 2025 and 2026 texts say
   `"how": "pdftotext -layout"`.
3. Put the four fixture pairs in `tests/documents/` (its README says which),
   run `python3 src/parse/extract_calendar_text.py --canary tests/documents`,
   and commit them on `dev`.
4. Run `python3 preflight.py` on the laptop, on `dev`. Windows has not run the
   new checks.
5. If you like, set `NIGHT_DOCUMENTS` to `shadow`, start the nightly on `dev`
   by hand with Dry run ticked and "Take the day's data" unticked -- so it
   asks the General Court nothing -- and read `text_canary` in its verdict;
   then delete the variable again. It is the repository's, shared by every
   branch: still set when `dev` merges, `main` uses it that night.
6. Merge to `main` with the variable unset. The night then differs only in
   its hours for the bill requests and the lists: the calendars' and
   journals' text stays the laptop's in the kit, and its verdict, its list
   and what seed-kit, pull and kit-up send are as they were.

After 10 November:

7. Set `NIGHT_DOCUMENTS` to `shadow` for three scheduled nights. Each
   verdict's `document_files` says what the night would ask, and
   `documents_held_back` names each document it would hold back for a
   person; `text_canary` should start "identical for 4 of 4" and name
   pdftotext 26.09.0; and `gc_requests` should be what it was. Warning signs:
   the would-ask count at its cap every night, any possible rename, any
   document of an older year. Documents merged before 26 October that share
   a path -- the 2026 Senate list's "No 21" and "No 18" with their
   supplements -- are named as held back: once the night fetches (step 9) its
   list gives the one still wanted a file of its own, and nobody need do
   anything. Two that share a path and are both held are named too ("both
   held"): one of them was never fetched. On the laptop, open the PDF at that
   path to see which document it is, then fetch the other with
   `python3 src/fetch/gc_web/fetch_calendar_archive.py --take "NAME"`, which
   saves it under its own name, run
   `python3 src/parse/extract_calendar_text.py`, and
   `python3 src/ops/cloud.py seed-kit`. The 2025 Senate list collides too,
   and the night no longer reads it, so it names none of these: SC027.pdf is
   the path of four documents ("No 27 June 19 2025" and three supplements of
   it) and SC024A.pdf of two. Check them the same way, now.
8. Make the texts the night's, once, before any number:
   - on the laptop, `python3 src/ops/cloud.py pull`, then
     `python3 src/parse/extract_calendar_text.py`, then
     `python3 src/ops/cloud.py seed-kit`, so the bucket holds every text and
     the laptop's record of what its drain fetched -- a document fetched here
     and not seeded is one the night asks for again;
   - then, on `dev`, change the texts' entry in `cloud_kit.json` (the one
     whose globs are the four `*.txt`) from `"owner": "laptop"` to
     `"owner": "night"`, and `KIT_TEXTS_OWNER` in `preflight.py` to match,
     in one commit; run `python3 preflight.py`, and merge to `main`.
   From that merge, seed-kit sends only a text the bucket does not hold, and
   pull takes the night's. Until it, a night whose switch is a number asks
   for no document and says so: "not fetching: the calendars' and journals'
   text is still the laptop's".
9. Set it to `1` for a week. The first night that carries each new kind of
   warning waits for your approval. If `document_files` says "failed: HTTP
   302", the General Court's viewer answers with a redirect, which the night
   does not follow -- nor asks for that document again: set it back to
   `shadow` and ask.
10. The laptop's routine from then: `cloud.py pull`, then `cloud.py
    docs-down`, which brings the night's PDFs; the committee reports read
    them by themselves. Whatever is fetched or decided here reaches the night
    only through the bucket, so each of these ends with
    `python3 src/parse/extract_calendar_text.py` and then
    `python3 src/ops/cloud.py seed-kit`:
    - a journal the night names as a possible rename:
      `python3 src/fetch/gc_web/fetch_calendar_archive.py --settle "NAME"` if
      it is the same journal, or `--take "NAME"` if it is not;
    - a document held back because its address is not the one its list
      gives, once a person has looked: `--take "NAME"`;
    - a document the night did not find (named in `document_files`, and
      marked gone): if the General Court's page still lists it and it opens
      there, `--take "NAME"`;
    - a document the night will not ask for again -- a refusal recorded, a
      dropped connection or a redirect, three tries: the drain, which takes
      them when a person runs it;
    - a document with no text the night could use: its warning says what to
      do for its cause. Two files of the person's are read from `main` and
      do nothing until merged there: `corrections/documents_without_text.json`
      for a document with no text in it, and
      `corrections/documents_with_text.json` for one whose text a person has
      read and accepts as its own though the night's test refused it; each
      is `{"calendars/2026/HC035.pdf": {"why": "...", "day": "2026-11-20"}}`,
      a document's PDF path, as the warning gives it, with why and the day.
11. Then `4`, then `8` before late November, when two years' lists are open;
    and, once the documents' warnings are familiar, ask for them to be exempt
    from the approval gate.

To turn it off: delete the variable, or set it to `off`. The next night asks
only what it asked before, and its verdict no longer says the switch; after
its next pull the laptop fetches this year's documents again. Run
`python3 src/ops/cloud.py docs-down` first, before any fetch of this year's
or last year's documents here, so that the laptop has the PDFs the night
fetched and the drain and the committee reports do not ask for them again.
The texts stay the night's in the kit; seed-kit still sends any the bucket
does not hold.

What the night itself asks, inside that window: the downloads page and the
day files, then next session's bill requests and the two index pages' lists
of calendars and journals -- each of those two only if it can finish by 12:00
UTC (8 a.m. EDT, 7 a.m. EST), since 26 October 2026, and stopped at its time
limit if it has not -- and, while the repository variable `NIGHT_DOCUMENTS`
is a number, up to that many new calendars and journals themselves, on the
same terms. The run's page on the Actions tab says what it asked, step by
step.

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

## Retired

- **`docket_chain.py`**, superseded by `gc_lane.py` and retired on 1 October
  2026, with `fetch_archive_text.py`, the two-request bill-text route its tail
  queued and `fetch_legislation.py` superseded on 10 September.
- **`captions_watch.py`**, the politeness loop for YouTube's captions, retired
  on 6 October 2026. Captions come through `livestreams.py` now.
- **`extract_watch.py`**, which wrote the text beside each calendar and
  journal PDF behind the calendar drain, retired on 6 October 2026. The drain is
  finished; `extract_calendar_text.py` is run by hand after a fetch of PDFs
  here, and `seed-kit` sends the text the bucket does not hold. GitHub's night
  makes the text of the documents it fetches itself, once `NIGHT_DOCUMENTS`
  is a number (`nightly.make_texts`).
- **`narrative_watch.py`**, stood down on purpose after it narrated 2015-2016
  from a half-complete database seed, retired on 6 October 2026. The archived
  terms are narrated by `build_all.py` (`narrative.py`, `narrate_archive.py`).

All four were deleted with `obsolete/` on 23 October 2026, and git history
keeps them and that folder's README. Nothing here starts any of them.
