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

**Check before you start one.** Two of the same watcher is two fetchers.

```
python3 -c "import subprocess;print(subprocess.run(['powershell','-NoProfile','-Command','Get-CimInstance Win32_Process | ? { $_.CommandLine -match \"watch|fetch_\" } | Select ProcessId,CommandLine | Format-List'],capture_output=True,encoding='utf-8').stdout)"
```

---

## `gc_lane.py` -- the one worker for the General Court

Runs the General Court's fetches one after another from `gc_lane.queue`, a
line per step (what would follow `python3`), and records each finished line
in `logs/gc_lane.done` so a restarted lane picks up where it was. Lines can be
added while it runs; an empty queue is waited on for twelve hours.

It holds `archive/.lock` for its whole life and touches it every minute, and
the fetchers check with `refusal.hold()` that their parent is the lane that
holds it -- because several fetchers never looked at the lock, and
`fetch_calendar_archive` deletes one more than an hour old. A step marked
`handover` takes the lock itself and is given it for that step. It stops on
any step that exits non-zero, and before every step if
`archive/refused.json` exists at all.

```
python3 watchers/gc_lane.py            # from the repository root
tail -f logs/gc_lane.log                # the lane; each step logs to logs/gc_<time>_<step>.log
```

`rest.py SECONDS label` is a pause the lane can run as a step, so the
address sees bounded runs with an hour between them rather than one crawl.

Started 11 September with the person's leave for that absence: the
2015-2016 docket, then bill text 2017-2024 in 800-request runs. What is
queued is in `gc_lane.queue`, with the reasoning beside each line.

## `captions_watch.py`

Asks YouTube for captions again every so often and drains a little when it says
yes. **YouTube, not the General Court** — it does not take `archive/.lock` and
does not contend with a docket or calendar fetch.

It is a politeness loop rather than a drain: YouTube answered 429 on the first
request at a twenty-second delay, which is a per-address throttle and not a
burst limit, so pacing alone will not get through it and hammering it is how an
address stops being served at all. It probes with a handful of requests and
backs off when refused.

```
python3 watchers/captions_watch.py          # from the repository root
tail -f caption_run.log
```

## `narrative_watch.py`

Watches for a docket file to finish and runs `narrative.py` over it.

It **skips `Docket_db_*.txt`**, the seeds read out of the database, and it
requires `logs/docket_chain.log` to say `<term>: done` before it will build a
term. Both guards exist because it once built 2015-2016 from a half-complete
database seed — the `Docket` view runs out part way through 2016 — and put ten
wrong passage rails on the live site, including HB148 showing a vote rail
beside the word "vetoed".

If you fetch a docket with the bare script rather than the chain, this watcher
will not act on it. Run `narrative.py` yourself, which is what happened for
2021-2022 on 10 September.

## `extract_watch.py`

Pulls text out of calendar and journal PDFs as they arrive. No network.

## `docket_chain.py`

**Superseded by `gc_lane.py`; do not start it.** It ran the archive fetches
one after another holding `archive/.lock`, and its tail queues bill-text runs
through `fetch_archive_text.py`, the two-request route `fetch_legislation.py`
superseded on 10 September. Its seed for 2015-2016 is also wrong: the
database's "2016" rows are the 2015 history of 190 carried-over bills, so
seeding from them skips those bills' whole 2016 record. The lane's queue
uses `Docket_db_2015.txt` instead. Kept for its reasoning.

## Not running, on purpose: `narrative_watch.py`

It narrates a docket the moment its fetch finishes. The 2015-2016 docket
now being fetched mixes the database's lines for 2015 -- which the
narrator's grammar fails on 42-64% of -- with web lines for 2016, and
narrating it unattended is how wrong passage rails reached the site on the
10th. Narrate it by hand once the grammar for the older lines is in.
