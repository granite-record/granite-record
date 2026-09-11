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

Runs the archive fetches one after another, holding `archive/.lock` so two
cannot overlap. **Not running**, and worth reading before it is: its tail end
queues bill-text runs through `fetch_archive_text.py`, which is the two-request
per-bill route that `fetch_legislation.py` superseded on 10 September — the
legislation path gets sponsors, committee, title, analysis and the full text in
one request, and every bill of every term from 1989 to 2026 now has an address.

Starting the chain unedited would spend days on the worse route.
