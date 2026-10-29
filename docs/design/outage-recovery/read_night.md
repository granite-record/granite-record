# The night on a refusal, end to end: run 151 (29 October 2026) and the nights after it

Read-only. Code read at `origin/dev` = HEAD `4590795`. Dev has moved one commit past the
`0702100` named in the brief: `4590795` is a How to Vote wording fix. The night ran
`main` at `6ab3380`. `git diff origin/main origin/dev` shows nothing for
`.github/workflows/nightly.yml`, `nightly.py`, `refusal.py`, `snapshot_gencourt.py`,
`workers/night-timer/`, `src/ops/cloud.py` or `netcheck.py`, so the line numbers below hold for
the code that ran. `feat/night-clock` was read at `84a81ee`.

Evidence used:
- the bucket's `state/refused.json`, `state/last-night.json`, `logs/2026-10-29/nightly-2026-10-29.log`,
  `state/census.json` and `state/last-weekly.json`;
- the R2 listing of `state/`, which holds no `sql-held.json`, so no hold on the SQL host stood;
- GitHub's API for run 40841071509 (run 151): its jobs, and every step's start and end time;
- the list of the nightly's recent runs.

Nothing was run against the General Court, and nothing was written outside `/tmp/claude-0/audit/wf19/`.

A note on clocks: the runner's clock is set to Eastern time (`nightly.yml:294-298`), so every
"at" written by the night is local time. `refused.json`'s `"at": "2026-10-29T04:27:14"` is
**08:27:14 UTC**. Its `epoch` is true UTC.

---

## 1. The machinery

### 1.1 Who starts a night, and how two are avoided

The Worker `graniterecord-night-timer` starts the night.
- Its cron is `"17 8 * * *"` (`workers/night-timer/wrangler.toml:10-11`).
- It lists the nightly's runs on `main` created today (UTC) (`index.js:51-59`). If any run has
  event `schedule`, or a title containing "(scheduled, by the timer)", it starts none
  (`startedToday`, `index.js:42-46`).
- Otherwise it dispatches `nightly.yml` on `main` with these inputs:
  `dry_run:"false", fetch:"true", preview:"true", new_term:"false", timer:"true"` (`index.js:29-30, 64-71`).
- It retries a failed dispatch at most twice, 20 s apart. It stops at once on 401, 403, 404 or
  422 (`index.js:33, 66-77`).
- It has one cron a day. **Nothing in it ever starts a second night after a failed one.**

GitHub's own cron is the fallback (`nightly.yml:121-122`).
- Its first job, `started` (`nightly.yml:199-225`), counts `workflow_dispatch` runs on `main`
  created today whose title contains "(scheduled, by the timer)". If there are any, the night
  stands down (`nightly.yml:232`).
- It counts by title, not by conclusion (`nightly.yml:217-219`). **So a timer night that failed
  still stands the fallback down.**
- The last three fallback runs started at 15:13, 14:33 and 15:07 UTC (runs 140, 148 and 150).
  Each stood down within seconds.

### 1.2 The workflow, job by job (`.github/workflows/nightly.yml`)

Run-level settings:

| What | Setting | Lines |
|---|---|---|
| Concurrency | a run of `main` that is not a dry run has a group of its own (its run id) | 143-145 |
| `FETCH` | true on a schedule, or from the box | 153 |
| `DRY_RUN` | false for a run of `main` with the box unticked | 174 |
| `REVIEW_GATE` | `"on"` | 184 |

The jobs:

| Job | Runs when | Machine and limits | Lines |
|---|---|---|---|
| `started` | only on a `schedule` event | ubuntu, 5 min | 199-225 |
| `night` | `!cancelled() && (not schedule \|\| by_timer == '0')` | `windows-2022`, **300 min**, concurrency `gc-night` (one at a time, never beside the weekly) | 227-618 |
| `publish` | `!cancelled() && needs.night.result == 'success' && publishable == 'true' && dry_run == 'false' && ref == main` | — | 650-792 |
| `keepalive` | schedule only | — | 800-819 |

The `publish` job goes through the `production` environment when the gate clears the night, and
through `production-review` otherwise (`nightly.yml:657`).

Steps of the `night` job, in order, with what each needs to run:

| # | Step | Runs when | Lines |
|---|---|---|---|
| 2 | Healthchecks `/start` | not a dry run | 267-286 |
| 3-7 | checkout, Eastern clock, Python, Node, pip | always | 288-329 |
| 8 | **state-down** (`cloud.py state-down`): `state/refused.json` becomes `archive/refused.json`, among the other state files | always | 331-340 |
| 9 | kit-down | always | 342-351 |
| 10 | captions inbox down | `FETCH`; continue-on-error; 10 min | 365-377 |
| 11 | livestreams (YouTube) | `FETCH`; continue-on-error; 80 min | 401-418 |
| 12 | **The night**: `python nightly.py --runner` | always | 437-445 |
| 13 | **A refusal goes to R2 at once** (`cloud.py state-up`) | `always() && statedown success && archive/refused.json exists` | 449-459 |
| 14 | preview deploy | `always() && built == 'true' && PREVIEW` | 464-472 |
| 15 | pack the site for the publish job | `success() && publishable == 'true' && not dry` | 481-492 |
| 16 | kit-up (logs, the archive, what changed) | `always() && kitdown success` | 506-519 |
| 17 | verdict (`nightly.py --runner --close`) | `always()`; exits 1 if any step it is told of failed | 521-532 |
| 18 | **state-up** | `always() && statedown success` | 534-543 |
| 19 | inbox-clear | after a successful kit-up; not dry | 554-565 |
| 20 | Healthchecks end ping | always; not dry | 568-618 |

The end ping (step 20) works like this:
- If `logs/alert.txt` is non-empty, the night's check gets `/fail`, with the alert as the ping's
  body (585-596).
- If `logs/alert-warn.txt` is non-empty and `HEALTHCHECKS_WARN_URL` is set, the warnings' check
  gets `/fail` (608-616).

The `publish` job is the only thing that pings `HEALTHCHECKS_PUBLISH_URL` (745-757). It goes
quiet whenever nothing is published.

**Retries.** No step and no job retries, and nothing re-dispatches a failed night. The verdict's
`"attempt"` is `GITHUB_RUN_ATTEMPT`, recorded and never read (`nightly.py:4962`). A person's
"Re-run failed jobs" would be attempt 2 of the same run. It would run state-down again, which
would now bring the bucket's refusal down, so it would meet `gc_quiet()` (§1.3) and ask nothing.

### 1.3 Inside `nightly.py --runner`: the order

1. `refusal.stand_down(...)` does nothing on GitHub's machine (`nightly.py:1437`; `refusal.py:473`).
2. The `.nightly.lock` file is taken (1466-1471). The log header is written (1481-1485).
3. `preflight.py --code` runs (1527-1530). It took **356 s** on the incident night (log line 1654).
4. If `--no-fetch` was given, the fetch block is skipped with "skipped: --no-fetch" (1536-1539).
   Otherwise **`gc_quiet()`** runs (1541; defined at 1233-1247):
   - any `archive/refused.json`, at any age, returns false with "a refusal is on file (...);
     clearing one is a person's decision, after netcheck.py";
   - a held `archive/.lock` returns false;
   - false means "FETCH DEFERRED" (1554-1557). Nothing at all is asked: not the export, not the
     database, not the bill requests, not the lists.
   - The docstring gives the rule: "a refusal on file, at any age, means no fetch tonight (a run
     nobody watches does not decide a refusal is over)" (28-29).
5. When `gc_quiet()` passes, everything below runs under `refusal.hold("nightly")` (1574):
   - the **try loop** (1575-1623): `snapshot_gencourt.py --dir nh-archive --into .`, with **no
     time limit** (1575-1578);
   - `fetch_status(rc)`, where rc 2 means "refused" (2749-2760);
   - the **break** at 1587-1589: `if (not a.runner or not got.startswith("empty") or refusal.MARK.exists()): break`;
   - only an export that came back *empty* goes on to `from_database` (1595-1615), at most once
     a night (`DB_AFTER_TRIES = 1`, `TRIES_AFTER_DB = 1`; 2611-2612);
   - after the loop, and only `if (rc == 0 or db_day) and not refusal.MARK.exists()` (1626):
     - the study committees' views, from the database (1627-1630);
     - the current term's data, from the database (1636-1638);
     - next session's bill requests, from the web (1641-1642);
     - the statutes, from the database (1645-1650);
     - the lists of calendars and journals, from the web (1653-1654).
     Each also re-checks `refusal.MARK`.
6. `installed = rc == 0 or db_day` (1658). The verdict's `fetch`, `files_from` and `tried` are set
   (1659-1702). On rc 2 the log says "REFUSED while fetching. Recorded; every fetch now waits for
   a person." (1704-1706).
7. The what-changed report runs only `if installed` (1715-1723).
8. **The build runs only `if installed or a.no_fetch`** (1726). That means
   `build_all.py --local --no-captions`, then `check_site`, then the census gates and the
   publish judgement (`Night.judge`, 5052-5216). Otherwise the log says "Nothing new was
   installed, so there is nothing to rebuild." (1804-1805).
9. `night.exit_code()` (5397-5404) is 1 whenever `problems()` (5217-5248) lists anything:
   - "the day's files: refused" or "the day's files: deferred: ..." (5224-5227);
   - "the build: not run" (5240-5241).
10. `finish()` writes `archive/last-night.json`, and the log is written last (1806-1856).

### 1.4 The export fetch, and how drops are counted (`src/fetch/gc_web/snapshot_gencourt.py`)

Before asking anything, the script:
- calls `refusal.check()` (517). `check()` stops only a record less than 24 h old
  (`refusal.py:106, 211-252`);
- takes `refusal.hold()` (518);
- stops if `refusal.MARK.exists()`, at any age (571-573).

**The page first.** `open_page()` (249-267) GETs `https://gc.nh.gov/dynamicdatadump/` with a
**300 s** timeout (231-232).
- Opening this page is what makes the General Court rebuild every table (217-230). It is the
  heaviest request of the night.
- A `"dropped"` answer here counts towards the two-drop rule (587-588).
- A *timeout* on the page is re-labelled `"slow"` and does not count (257-262). A reset or an
  unanswered close does count.

**Then the 14 files.** Each request is preceded by a jittered pause of `4 s × U(0.75, 1.25)`
(500-501, 592). Each is read once by `read_one()` (333-349), with `get()` timing out at
**120 s** (277-280). The answer is judged by `refusal.classify()` (`refusal.py:269-307`):

| Kind | What it covers | Lines |
|---|---|---|
| `refused` | HTTP 403, 429 or 503; any `Retry-After`; or the firewall's block page served as 200 (`BLOCKED = "Web Page Blocked\|Attack ID"`) | `refusal.py:265, 286-293, 303-306` |
| `dropped` | `RemoteDisconnected`, a reset, an abort, a refused connection, a timeout, an SSL EOF | `refusal.py:296-301` |
| `missing` | 404 or 410 | — |
| `failed` | anything else | — |

What the snapshot does with each answer:
- **`refused`**: `refusal.note()` at once and stop (`snapshot_gencourt.py:614-617`). The block
  page on the data page itself is handled the same way (584-586).
- **`dropped`**: `dropped += 1`. At 2, `refusal.note()` and stop (618-623). The first drop *on a
  file* gets one retry of that file after **60 s** (624-630). A first drop on the *page* gets no
  retry. It simply makes the first file's drop the second.
- When it stops, nothing is installed: "a build from some of tonight's files and some of an
  earlier day's is a record of no day" (679-681). Exit 2 means refused (682-685).

**The record keeps no kind.** `refusal.note(where, why)` writes only `at`, `epoch`, `where` and
`why` (`refusal.py:113-125`). The incident's record says
`"why": "RemoteDisconnected: Remote end closed connection without response"`, and nothing in it
says whether that was a drop or a 403. The kind is known at each of `snapshot_gencourt`'s three
`note()` calls (585, 615, 621) and then thrown away. There are 55 `refusal.note(` call sites
across the fetchers.

On GitHub's machine `note()` does not send the record to the bucket: `_governing()` is None when
`GITHUB_ACTIONS` is true (`refusal.py:126, 556-557`). The workflow's step 13 sends it, after
`nightly.py` exits.

### 1.5 Exactly why "a refusal on file" stops the database fallback

The SQL host is a different server.
- `fetch_day_db.py` never calls `refusal.check()` (`fetch_day_db.py:63-66`).
- `probe_db` keeps its own hold, which expires and lengthens: 20, 44, 92 and then 164 hours, with
  one connection tried a night (`probe_db.py:75-103`). It says outright: "A refusal from the web
  server does not hold this host, and the reverse."

Nothing technical ties the two hosts together. The stop is a rule the person decided ("carrying
on by another door is a person's decision"), and it is enforced at five places:

1. **The try loop sends only an "empty" export to the database** (`nightly.py:1587-1589`). A
   `refused` try breaks out before `from_database` is reached. On 29 October `from_database` was
   **never called**; the verdict's `tried` has one line, "the export, try 1: refused".
2. **`from_database()` refuses on its own** (3011-3015). If `refusal.MARK` exists, it logs "not
   asked: a refusal from the web server is on file, and carrying on by another door is a
   person's decision" and returns False. `fetch_day_db.py:63-66` restates the rule: "nightly.py
   will not START this with a refusal on file, which is the person's rule about carrying on by
   another door."
3. **Every database step after the loop needs `not refusal.MARK.exists()`**: the study views
   (1626), the term data (1636) and the statutes (1645).
4. **The next night stops before the loop.** `gc_quiet()` (1233-1242) is false on any
   `refused.json`, so nothing asks the database either.
5. **The weekly stops its database-only steps too.** `weekly()` defers everything on `gc_quiet()`
   (5981-5985): committee members, former members, study views and statutes are all database
   pieces (5987-6003). Only `fetch_committees.py` asks the web.

`preflight` holds all of this (`_nightly_falls_back`, `preflight.py:89426` onward):

| Run | What preflight requires | Lines |
|---|---|---|
| 310 | a refusal on file: the night asks neither the export nor the database (`fetch` starts with "deferred") | 90012-90018 |
| 311 | a refused export: the database is not asked | 90019-90024 |
| 314 | an export that *dropped* (did not complete): no fallback, and no second ask | 90075-90080 |
| 317 | a refusal recorded during a pass that still reads as empty: the database is not asked | 90112-90130 |

Run 317 also calls `from_database()` directly. **Any design that lets the database run during a
web refusal changes checks that preflight holds today.**

### 1.6 What is built and published when nothing is installed

**Nothing is built and nothing is published.** `installed` is False, so the build branch at 1726
is skipped. `built` stays false, so the preview step (`nightly.yml:466`) and the pack step (483)
are skipped. The night step exits 1, so `needs.night.result` is `failure` and the publish job is
skipped (653).

Neither yesterday's data nor any newer code on `main` is re-published. The site stays at the
last published build: 28 October's, run 149 (census `day: 2026-10-28`, fingerprint
`22360e1824b829fe`).

The only existing way to publish during a refusal is a person's run by hand of `main` with "Take
the day's data" unticked and Dry run unticked:
- the run gets `--no-fetch` (`nightly.yml:441`), so `gc_quiet()` is never consulted
  (`nightly.py:1536-1539`) and livestreams are skipped (`nightly.yml:403`);
- it builds from the kit, and `problems()` skips the fetch checks (5224);
- it is publishable unless production already serves the same fingerprint *and* the same
  commit (`already`, 5129; the fingerprint covers `meta.json`, the bill index, `home.json` and
  `legislators.json`, 1330-1358).

So with no new data and no new code it would publish nothing. A release still waits in
`production-review` unless a dry run of the same commit proved it (5169-5177; `release_reasons` 4606).

### 1.7 Verdict, alerts, Healthchecks, email

The verdict:
- `--close` (`close_verdict`, 5779-5887) folds in the workflow's step results. Any failed step
  makes it not clean, and the step exits 1 (5841-5856, 5887).
- `alerts_of()` (5750-5777) collects, in order:
  - a refusal on file ("... Every fetch waits until a person clears it: python3 netcheck.py ...
    then python3 src/ops/cloud.py clear-refusal."; 5758-5763);
  - a hold on the SQL host;
  - a check of the built site that holds the night;
  - "The night was not clean: " followed by `plain_why()`.
  These go to `logs/alert.txt` (5720, 5857-5862).
- `warns_of()` goes to `logs/alert-warn.txt` (5721, 5733-5747).

Email:
- **The only email the night causes is Healthchecks'.** There is no SMTP or other sender in
  `nightly.py` or `cloud.py`.
- The night's check emails when it goes down, and again when it comes back. The code's own
  comment says so: "a refusal held for three nights is one email" (5686-5689).
- The publish check (`HEALTHCHECKS_PUBLISH_URL`) is pinged only by a publish that landed. It goes
  down, and emails, once its period runs out. The period is set in Healthchecks, not in the
  repository. `nightly.yml:759-761` says a missing ping once took "two days" to be reported.
- The docket "not moving" warning waits 42 days in the interim season (`STILL_DAYS`, 3405-3407),
  so it says nothing for weeks.

### 1.8 How the refusal record travels

- **On the runner.** `state-down` takes each state file the bucket holds (`cloud.py:1995-2047`).
  The state list is in `cloud_kit.json:196-198`, whose entry for `refused.json` reads "nothing
  asks the General Court, from either machine, until a person clears it". Step 13 and step 18 run
  `state-up` (`cloud.py:1627-1690`).
  - `state-up` sends a file only where the bucket holds none, or where this machine changed it
    and the bucket did not.
  - **It never removes a file from the bucket**, and never re-sends one a person cleared
    (1630-1640, 1659-1666).
  - So deleting `archive/refused.json` on the runner would *not* lift the bucket's copy.
- **Lifting.** Only `cloud.py clear-refusal` lifts the bucket's copy (2049-2135). It moves the
  object to `replaced/<day>/`, records the cleared sha so that no `state-up` re-sends it, and is
  run by a person on the laptop. The laptop's own copy is cleared by `refusal.py --clear`
  (`refusal.py:839-858`).
- **The laptop.**
  - `cloud.py pull` brings the bucket's refusal down (`pull_refusal`, `cloud.py:2754-`).
  - A stood-down laptop may not start any General Court request inside the night window,
    08:00-13:30 UTC, or in the 30 minutes before it (`refusal.py:520-533, 707-729`).
  - Nor may it start one until it has read the bucket's record since the last window closed
    (730-743).
  - Its hand fetches are stopped for 24 h. The lane is stopped by any `refused.json` (`force()`,
    `refusal.py:195-208`).

---

## 2. The incident night, minute by minute (29 October 2026)

All UTC; Eastern (EDT) in brackets. Step times come from GitHub's API; the rest from the log, the
verdict and the code.

| UTC (EDT) | What happened | Where |
|---|---|---|
| 08:17:00 (04:17) | The timer's cron fires. It lists today's runs, finds none, and dispatches `nightly.yml` on `main` with the scheduled night's boxes. | `wrangler.toml:11`; `index.js:51-71` |
| 08:17:24 | **Run 151** (id 40841071509) is created: event `workflow_dispatch`, title "nightly (scheduled, by the timer)", attempt 1. `started` and `keepalive` are skipped (not a schedule event). | API; `nightly.yml:47, 201, 232, 802` |
| 08:17:32-34 | Healthchecks `/start`. | `nightly.yml:267-286` |
| 08:17:34-08:18:30 | Checkout, Eastern clock, Python, Node, packages. | 288-329 |
| 08:18:30-34 | **state-down.** The bucket held no `refused.json`; had it held one, the night would have deferred. | 331-340 |
| 08:18:34-08:21:08 | kit-down. | 342-351 |
| 08:21:08-12 | Captions inbox down. Livestreams succeed with "deferred": YouTube's own hold lasts until 2026-11-03 06:20 UTC (verdict `captions.why`). | 365-418 |
| 08:21:12 (04:21) | `nightly.py --runner` starts. Its log header reads "2026-10-29 04:21". | `nightly.yml:437-445`; log lines 1-5 |
| 08:21:13-~08:27:08 | `preflight.py --code`: 356 s, exit 0. | `nightly.py:1527-1530`; log line 1654 |
| ~08:27:08 | `gc_quiet()` passes: no refusal, no lock. `refusal.hold("nightly")` is taken. | 1541, 1574 |
| ~08:27:08 | `snapshot_gencourt`: `check()` and `hold()` pass; no `refused.json`. | `snapshot_gencourt.py:517-518, 571` |
| ~08:27:08-10 | **Request 1:** GET `https://gc.nh.gov/dynamicdatadump/` gives `RemoteDisconnected` within seconds. That is "dropped", and not "slow" because it was not a timeout. `dropped = 1`. | 578-588; `refusal.py:296-299`; log line 1657 |
| +3-5 s | The jittered pause. | `snapshot_gencourt.py:592` |
| ~08:27:14 | **Request 2:** GET `.../Docket.txt` gives `RemoteDisconnected`. `dropped = 2`, so `refusal.note("snapshot_gencourt", why)` writes `archive/refused.json` (`"at": "2026-10-29T04:27:14"`). Because this was the second drop, the file's one 60 s retry is not reached. | 603-623; log line 1658 |
| 08:27:14 | Manifest written. "Nothing installed into .: 0 of 14 files arrived". Exit 2. The step took 6 s. | 653-685; log lines 1660-1666 |
| 08:27:14 | `fetch_status(2)` returns "refused"; `tried = ["the export, try 1: refused"]`. The loop breaks, so **the database is never asked**. The gate at 1626 fails, so the study views, term data, bill requests, statutes and lists are all skipped. `installed = False`; `files_from: none`. "REFUSED while fetching." | `nightly.py:1580-1589, 1626, 1658-1706` |
| 08:27:14-15 | No what-changed report and no build: "Nothing new was installed, so there is nothing to rebuild." `exit_code` is 1 (problems: "the day's files: refused", "the build: not run"). Verdict and log written; "finished 04:27, 6 min, exit 1". | 1715, 1726, 1804-1805, 5217-5241, 5397-5404 |
| 08:27:15-20 | Step 13, **"A refusal goes to R2 at once"**: `state-up` creates `state/refused.json` in the bucket. | `nightly.yml:449-459`; `cloud.py:1627-1690` |
| 08:27:20 | Preview and pack are skipped (nothing was built). | `nightly.yml:466, 483` |
| 08:27:20-55 | kit-up: the logs, `logs/2026-10-29/nightly-2026-10-29.log` and `preflight-last.json`. | 506-519 |
| 08:27:55 (04:27:55) | **Verdict** (`--close`): `night=failure` is folded in, so not clean, and the step itself fails (exit 1). Alerts: the refusal line, and "The night was not clean: The General Court refused a request. Nothing more was asked, and every fetch waits until a person clears the refusal. Nothing was published." Warn alerts: the captions inbox line. | `nightly.py:5779-5887, 5750-5777, 2283-2285` |
| 08:27:55-59 | state-up: `last-night.json`, `livestreams.json` and the rest. | `nightly.yml:534-543` |
| 08:27:59-08:28:01 | inbox-clear. | 554-565 |
| 08:28:01-03 | Healthchecks: the night's check gets `/fail` with the two alert lines as its body (an email if the check was up). The warnings' check gets `/fail` if its secret is set (it was probably already down for the captions inbox; not verified). | 568-618 |
| 08:28:07 | **The publish job is skipped** (`needs.night.result == 'failure'`). The publish check is not pinged. | 653, 745-757 |
| afternoon (not yet at 12:49 UTC, when this was checked) | GitHub's scheduled fallback, when it comes, will find run 151 by its title and stand down, although run 151 failed. *Inferred from the code and the last three days' pattern (14:33-15:13 UTC).* | `nightly.yml:216-225, 232` |
| ~8 h later | netcheck.py, run once by hand from a cloud container, got 200s over HTTPS on both hostnames. netcheck writes nothing (`netcheck.py:8-9`), so the bucket's refusal stands. | — |

Note on the netcheck result. A 200 from another machine shows that the server was answering.
It does not show that **GitHub's runner** would have been answered. *Inference, not shown by any
log:* GitHub's hosted runners draw their addresses from a shared pool, so the address that met
the drops is not known, and tomorrow's runner may well have a different one. The refusal was
recorded about "this address" (`refusal.py:24-27`), but on GitHub "this address" is not one
fixed address.

---

## 3. The nights after it, with `state/refused.json` standing

Every night is the same until a person runs `refusal.py --clear` and `cloud.py clear-refusal`.

**30 October, 08:17 UTC (04:17 EDT).**
- The timer dispatches. Yesterday's run is not "today", so `index.js:42-46` does not stop it.
- state-down brings the refusal down as `archive/refused.json`. kit-down, the inbox and
  livestreams (YouTube) run as usual.
- `nightly.py` runs **preflight anyway** (about 6 min; 1527) and **then** `gc_quiet()` returns
  false. The log says "FETCH DEFERRED: a refusal is on file (snapshot_gencourt at
  2026-10-29T04:27:14); clearing one is a person's decision, after netcheck.py" (1541, 1554-1557).
- **Nothing is asked of anyone at the General Court**: not the website, not the SQL host.
  Nothing is built (1726), and the verdict's `fetch` is "deferred: ...".
- `plain_why`: "The day's files were not asked for: a refusal on file or another fetch was in the
  way." (2317-2318). Exit 1.
- Step 13 runs again because the file exists. `state-up` finds it "unchanged" (`cloud.py:1655-1658`).
- No preview, no pack, no publish.
- Healthchecks gets `/fail` again. **By the code's comment, that is no new email** (5686-5689).

**31 October.** The same.

**1 November.** The same. Daylight time ends at 06:00 UTC (`refusal.py:635-651`), so 08:17 UTC
is now 03:17 EST.

**Monday 2 November, 04:17 UTC.** The weekly (`weekly.yml:51`) defers everything, its
database-only pieces included (`nightly.py:5981-5985`). Not clean.

**Meanwhile**:
- **The site.** It serves 28 October's build every day. Code merged to `main` (the 1 November
  release, the night clock) is **not published either**.
- **The publish check.** It goes down once its Healthchecks period runs out. That is the second,
  and last, email (the period is not in the repository).
- **The laptop.** Its pull brings the refusal down. The lane stops at it, and hand fetches stop
  for 24 h.
- **A stood-down laptop is not a way round.** It does not run the night, the snapshot or publish
  at all (`refusal.stand_down` at `nightly.py:1437` and `snapshot_gencourt.py:515`).

**The day a person clears it.**
- `clear-refusal` moves `state/refused.json` to `replaced/<day>/` (`cloud.py:2099-2108`).
- The next timer night (08:17 UTC) asks the export as normal. A run by hand that morning would
  too.

---

## 4. What `feat/night-clock` (84a81ee) changes in this flow

The diff touches `nightly.py`, `preflight.py`, `ARCHITECTURE.md` and `tests/rehearse_turn.py`.

**It adds:**
- `ASK_UNTIL = (12, 0)` in UTC, and `asking_left(minutes)`. That function returns a deadline
  only if `refusal.night_window()` places the clock inside the daily 08:00-13:30 window and
  `now + minutes` falls *before* 12:00. It reads the clock in UTC through `refusal._utc()`,
  never the runner's Eastern clock.
- `seconds_left(deadline)`.
- `run(..., timeout=)`, which kills the child process at the limit and returns
  `RUN_KILLED = 124`.
- `LSRS_MINUTES = 5` and `LISTING_MINUTES = 7`.
- `clock_kind()`, so that a clock's "not asked for" warning never holds the gate
  (`warning_reasons`).

**It gates only two steps:**
- `take_lsrs()` (the bill requests);
- `take_documents()` (the calendar and journal lists).
  Each says "not asked for: it is HH:MM UTC, ..." and keeps the copy on file.

**It leaves alone:**
- `gc_quiet()`, the try loop, `snapshot_gencourt`, `from_database` and `refusal.py`.
- The export. Its docstring says so: "The day's files keep their own rule and not these hours:
  a night GitHub starts late still asks the export whenever it runs." The export step still has
  no time limit.

**Its reason for 12:00** is the night's own path: "a refusal met on the night reaches the bucket
only once nightly.py exits, after the build, and a stood-down laptop may pull and start from
13:30".

**Effect on 29 October: none.**
- The two gated steps already sit behind `not refusal.MARK.exists()` (1641, 1653).
- On the following nights `gc_quiet()` stops everything before them.
- A "not asked for" would never hold a publish, but there is no publish to hold.

**What it gives a self-healing design:**
- a tested "may a request still start and end before 12:00 UTC" gate (`asking_left`);
- a kill counted from the moment the gate read the clock (`run(timeout=seconds_left(...))`).

Both apply directly to a second attempt later the same morning (hook (b)).

---

## 5. Candidate hook points

### (a) An automatic, minimal re-test of the connection

**Where the decision is made.** `gc_quiet()` (`nightly.py:1233-1247`) is the one gate. The night
calls it at 1541 and the weekly at 5981. Today it is false on any `refused.json`, so a re-test
belongs at its start.
- It runs only on GitHub's runner and only once preflight has passed.
- It must run under `refusal.hold("nightly")` (1574) and the `gc-night` concurrency group
  (`nightly.yml:246-248`).
- Today the hold is taken *after* `gc_quiet()`. A re-test inside it would need the lock taken
  first.

**What it needs first: the record must say what kind of refusal it was.**
- Add a `kind` to `refusal.note()` (`refusal.py:113-125`), and pass it from
  `snapshot_gencourt.py:585` (block page), `:615` (403/429/503/Retry-After) and `:621` (second
  drop).
- A record with no `kind` must be read as a true block: there are 55 `note()` call sites, and
  every record written before the change has none.
- Escalation state (re-tests made, when the next one is due) also needs a home, either in the
  record or beside it. `probe_db`'s hold (`probe_db.py:75-103`: 20, 44, 92, then 164 h, one
  connection per expiry, a rejected login treated apart) is the project's own working precedent
  for a hold that expires and lengthens. It argues: "a month unattended needs it, and one
  connection a night is not what that rule exists to prevent".

**What the knock should be.**
- **One** GET, from **the runner**, of a URL the night already fetches.
- Never an invented path. The first block was earned "for probing filenames that did not exist"
  (CLAUDE.md:56-57).
- Never the `dynamicdatadump/` page, which makes the General Court rebuild every table and may
  take up to 300 s (`snapshot_gencourt.py:217-232`).
- Judge it with `refusal.classify()` (`refusal.py:269-307`):
  - a page (no error and no block page) means the hold may lift;
  - "dropped" means the hold lengthens;
  - "refused" (403, 429, block page) turns the hold into a person-only refusal.
- *Guess:* `https://gc.nh.gov/downloads/Members.txt` (the snapshot's `EXTRA`,
  `snapshot_gencourt.py:122`) is a small file and may be static. Nobody has checked whether it
  is.
- **`netcheck.py` is not this.** It sends 8 requests to two hostnames, plain http and HTTP/1.0
  included, 3 s apart (`netcheck.py:8, 123-165`). It prints prose and always exits 0, and CLAUDE
  lists it among the scripts to ask before running.

**How a lift would reach the bucket.**
- The runner cannot lift the bucket's copy by deleting its own: `state-up` never removes, and it
  skips a sha a person cleared (`cloud.py:1630-1640, 1659-1666`).
- It needs a runner-side counterpart to `cmd_clear_refusal` (`cloud.py:2049-2117`). That would
  move the record to `replaced/`, record the lift *as the machine's, with the knock's answer*
  (not as a person's clear), and be called from a workflow step.
- `nightly.yml:449-459` decides whether to send by whether the file exists. That would need to
  learn the new state.
- The laptop is safe against racing it: it is held inside the window until 13:30 UTC and must
  pull afterwards (`refusal.py:520-533, 730-743`).

### (b) A second attempt later the same morning, inside the window

**In the same job.** This is the smallest change.
- The try loop (`nightly.py:1572-1623`) already knows how to wait and ask again: `EMPTY_WAIT = 30`
  minutes and `time.sleep` at 1622, for an empty export.
- A `refused` try breaks at 1587-1589. A drop-only refusal could get exactly **one** more pass
  after a long wait. A 403, 429, 503 or the block page never would.
- Gate that pass with `asking_left(minutes)` from `feat/night-clock`, and kill it at
  `seconds_left(deadline)`.
- The snapshot needs a time limit of its own for this. It has none today (1575-1578).
- *Arithmetic, not measured:* the worst case is the page's 300 s, plus 14 × 120 s, plus 14 × ~5 s
  of pauses, which is about 34 min. So the gate's minutes should be at least about 35.
- The note must be written only after the second pass fails, or the first record must be kept
  as provisional until then. Today `note()` is called at once (`snapshot_gencourt.py:620-621`).

**On 29 October's times.**
- The refusal came at 08:27 UTC; the clock's 12:00 left **3 h 33 min**.
- The job's 300 min (`nightly.yml:234`) run from 08:17 to 13:17. The build takes under 30 min
  (`nightly.yml:435-436`).
- So one re-try at around 10:00 UTC, then a build ending around 10:45, would have fitted easily.
- The cost is a `windows-2022` runner sitting idle while it waits. *Whether those minutes cost
  anything here is not established.*

**As a second dispatch.** This needs more change.
- The timer's `startedToday` (`index.js:42-46`) would refuse a second run, because it counts any
  run created today.
- The fallback's `started` (`nightly.yml:217-219`) counts timer-titled runs regardless of their
  conclusion.
- So a second dispatch needs its own input, its own title, and both dedupe checks taught about
  it.
- "Re-run failed jobs" will not do either: it meets the refusal now in the bucket (§1.2).

**The workflow's own steps.** Step 13 runs only after `nightly.py` exits. An in-job wait
therefore delays the refusal reaching the bucket. That does not matter before 12:00, because the
laptop is held until 13:30.

### (c) The database as the night's source while the web server is out

**Where.** The five gates in §1.5:
- `nightly.py:1587-1589`;
- `3011-3015`;
- `1626 / 1636 / 1645`;
- `gc_quiet()` at `1541`;
- `weekly()` at `5981`.

**The change.** `gc_quiet()` would return two answers, one for the web server and one for the
SQL host. A refusal whose recorded kind is "dropped" would leave the SQL host open; a true block
would keep both closed until a person decides.
- `from_database()` would be allowed when the record is a drop-kind refusal, and the loop's break
  would be taught that case. Today only `got.startswith("empty")` reaches it.
- The study views, term data and statutes would follow. The bill requests (1641) and the lists
  (1653) ask the web server and stay off.
- The weekly's database pieces (5987-6003) likewise.
- `probe_db`'s own hold still governs the SQL host, whatever is decided.

**What the database night gives** (`nightly.py:305-385`):
- 7 of the 14 files, rebuilt and guarded against the installed ones;
- `Members.txt` from the website, or else the installed one stays (3086-3108);
- the 6 lookup files carried over;
- `DB_NIGHTS_MOST = 7` nights in a row is an error on the page (1084).
- It needs the installed files, which the kit brings.

**What would change in preflight.** Runs 310, 311 and 317, and the direct call
(`preflight.py:90012-90024, 90112-90130`), assert the opposite of this. The change is therefore
the person's rule changing, which is the owner's OK the brief names. The IT office's September
answer about PublicSQL is the evidence for asking.

### (d) Publishing what can be published

**Today.**
- No build without an install (`nightly.py:1726`), and exit 1 (5224-5241).
- The preview (`nightly.yml:466`), the pack (483) and the publish job (653) are all skipped.

**The hook.**
- After the fetch block: when the refusal is drop-kind, or (c) installed the database's files,
  build from what is installed.
- Let `problems()` treat the refused export as a **warning**, the way a database night's export
  failure already is (`from_db()` at 2362, `KIND_FROM_DB` and `KINDS_FALLBACK` at 946, which
  "never hold"; `warned()`, 5258-5275).
- The census gates, `check_site` and the publish job then work unchanged.
- Whether such a night may publish itself, or waits in `production-review`, is the gate's
  question. A new warning kind holds a night today (`warning_reasons`).

**What it is worth.**
- With no new data and no new code, production already serves the same fingerprint and commit,
  so `publishable` is False ("already serves this build", 5129, 5196, 5201).
- So (d) alone mostly matters for **code merged to `main`**, which a refusal now keeps off the
  site, and as the way **(c)'s data** reaches the site.
- *Not established:* whether anything date-relative in `home.json` changes the fingerprint day to
  day.

**The person is still told.** `alerts_of()` puts the refusal line in the alert on every night
it stands (5758-5763), whatever the night does. A self-publishing night with a standing refusal
would still turn the night's check down and send the person an email.

---

## 6. The owner's idea (live updates as the signal), as far as the code and the design show

All of the following is from `/tmp/claude-0/audit/wf16/design_final.md` and the branches. None of
it is built.

**What the live Worker can and cannot see.**
- It reads PublicSQL and YouTube only: "ask gc.nh.gov" is under "What it never does" (§0). So
  **it cannot see the web server that dropped**, and its health says nothing about whether
  gc.nh.gov will answer GitHub's runner.
- It runs on Cloudflare's addresses: a third network, neither GitHub's nor the laptop's.

**It would not have been reading on 29 October.**
- Outside a sitting it reads on its "heartbeat" only from 1 January to 30 June, or in the 14 days
  after a day the chamber was hot.
- "Heartbeat and warm reads never start inside a window" (§2.3).
- So at 08:00-13:30 UTC on 29 October it would not have read anything.

**It is not finished.** Its SQL half waits on the November TDS and encryption test (§2.7). The
`live/tds` branch tip is `185a9f2` "WIP: ... (unreviewed, untested)". It writes to a second
bucket, `graniterecord-live`. *Guess:* the night has no credentials for that bucket today.

**Where it does help:**
1. It would be a frequent, cheap, independent record that **PublicSQL answered** (its
   `state.json` status and Healthchecks body, §2.6). That is evidence for hook (c): the night
   could see that the SQL host had been answering minutes before, without asking it first.
2. **During a sitting** it keeps the session-day page and the live votes current while the night
   is stalled (§4.2, §4.4). Readers would see the day's roll calls even on a morning the night
   cannot reach the website.
3. Its holds already follow the self-expiring, never-a-person rule for PublicSQL (§2.6 table).
   That fits the IT office's answer, and matches what (c) would do on the night's side.

**What it cannot do:** prove that gc.nh.gov is back. That takes a knock on the web server itself,
from the runner that will fetch: hook (a), or the second pass in (b).

---

## 7. Facts that constrain the design, and plain guesses

1. **Drops are this address's documented sign of refusing** (`refusal.py:274-276`, `netcheck.py:11-19`).
   - `netcheck.py` records an earlier episode in which every request was closed this way,
     "single probes with nothing else going". The file does not say whether that episode was
     one of the two blocks, or how long it lasted.
   - So treating drops as "may resume" is a bet, and the design must bound it: one knock, long
     waits, escalation.
2. **The data page counted as the first drop.** Request 1 was the page (`snapshot_gencourt.py:587-588`),
   which made Docket.txt's drop the second, and that refused at once. Had the page's drop not
   counted, Docket.txt would have had its one retry after 60 s (624-630).
3. **503 is lumped with 403 and 429 as "refused" today**, and so is any `Retry-After`
   (`refusal.py:272-273, 286`). The comment at 261-263 reads "a server shedding load says 503
   with a Retry-After, which is a request to go away, not a flaky link". Whether 503 may resume
   by itself is a decision for the design, not something the code settles.
4. **The scheduled fallback is no second chance.** It stands down for any timer run of the day,
   failed or not (`nightly.yml:217-219`).
5. **Preflight runs before the refusal gate.** Every deferred night still spends about 6 min on
   preflight and about 2.5 min on kit-down (1527 before 1541) before doing nothing.
6. **Guesses:**
   - the GitHub runner's address differs from night to night;
   - Healthchecks' "one email per change" (that is the code's own comment, not observed here);
   - the publish check's period;
   - the time of today's fallback stand-down;
   - whether `Members.txt` is a static file.
