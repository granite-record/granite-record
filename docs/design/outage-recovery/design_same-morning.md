# Back the same morning: two knocks inside the night's own job

Read-only design, 29 October 2026. Angle: **recover the same morning, not the next day.**

**Code read**
- `dev` at `4590795`, which is `0702100` plus one How to Vote text commit. That commit touches none of the files below. The night that ran was `main` at `6ab3380`. The readers found no difference from `dev` in `nightly.yml`, `nightly.py`, `refusal.py`, `snapshot_gencourt.py`, the night-timer or `cloud.py`.
- `origin/feat/night-clock` at `22d19e4`. That is `84a81ee` plus a merge of dev and the stamps. Line numbers marked **nc** are that branch's; bare numbers are dev's.

**Evidence**
- From the bucket, read only:
  - run 151's log, `logs/2026-10-29/nightly-2026-10-29.log`, lines 1656-1666;
  - its verdict `state/last-night.json`, and `state/refused.json`;
  - 28 October's log `logs/2026-10-28/nightly-2026-10-28.log`, used for step durations. It is downloaded to `r2_morning/` and deleted when this is done.
- The four readers' reports in this folder.

Nothing asked the General Court, the SQL host or YouTube. Nothing tracked was edited. **"Guess"** marks anything the code, the logs or the history do not show.

---

## 0. On one page

**The method.** When GitHub's scheduled night has its own two connections dropped by the General Court's web server, it asks again later **in the same job**, one request at a time:
- the first knock comes **60 minutes** after the refusal, and a second **90 minutes** after that if needed;
- each knock is **one GET of `Counties.txt`**, a 195-byte file the export serves every night;
- the night stays on the same runner, under the same lock, inside `feat/night-clock`'s 08:00-12:00 UTC hours.

When a knock is answered, the night lifts its own record, moving it aside and never deleting it, then asks the export **once more** and carries on exactly as on any night. The site is about an hour or two late instead of a day or more.

When neither knock is answered, the night ends as it does today. The record goes to the bucket carrying what the morning tried. Then either:
- **phase 1:** a person clears it, as today; or
- **phase 2:** the next nights test it once a night on a lengthening ladder, and after that it is a person's (§3).

| | |
|---|---|
| Who starts the second attempt | nobody new: **the same `nightly.py --runner` process**, which waits inside its `refusal.hold("nightly")` and inside the `night` job's `gc-night` group |
| Which refusals | only two **dropped** connections, met by the snapshot of **this run**, on a night **the schedule or the timer** started, not a dry run, not a New term run |
| The knock | `GET https://gc.nh.gov/dynamicdatadump/Counties.txt`, the snapshot's own User-Agent, 60 s socket timeout, no redirect followed, killed at 2 min |
| When | the refusal + 60 min, then + 90 min more. Each only if the knock **and** an export after it (2 + 40 min) can end before **12:00 UTC** (`asking_left`, nc `nightly.py:3923`) |
| Most requests a morning can add | **2 knocks**, plus **one** export pass (15 requests) that only an answered knock earns |
| What it never asks | the data page `dynamicdatadump/` as a knock, an invented path, another host, `netcheck.py`'s eight requests, anything from another machine |
| What stays a person's | a 403, a 429, the block page or a redirect, on the night or on a knock; any refusal from the laptop, a dry run, a New term run or a run by hand; any record with no `kind`, **the standing 29 October record included**; and, in phase 1, any refusal the morning did not lift |
| Bucket, laptop, workflow logic, `cloud.py` | **phase 1 changes none of them.** A morning lift happens before the record ever reaches the bucket (`nightly.yml:449-459` sends it only after `nightly.py` exits) |
| Depends on | `feat/night-clock` (`asking_left`, `seconds_left`, `run(timeout=)`), so it is built after that branch merges |

**29 October under it.**
- The refusal came at 08:27:15 UTC. The first knock would have come at **09:27:15**, the second at **10:57:20**.
- If either was answered, the site would have been live at about 10:25 or 11:55 UTC (06:25 or 07:55 EDT) instead of not at all.
- Whether either would have been answered is a **guess**. The only evidence is the manager's single, unlogged netcheck from another machine about eight hours later.

---

## 1. Who starts the second attempt

| Starter | Same address as the drops? | One at a time | New secret, permission or check | Extra cost | Reaches a lift how |
|---|---|---|---|---|---|
| **The same job, same process (chosen)** | **Yes.** Same runner VM for the job's life (*guess*: a VM's outbound address is stable while it lives; no log records it) | Same process and lock (`refusal.hold`, `refusal.py:320-436`) and the same `gc-night` job (`nightly.yml:246-248`). No second run exists | none | an idle `windows-2022` runner for ≤ 2.5 h (*guess*: free if the repository is public; not checked) | locally, before the record is ever sent, so **no bucket change** |
| Night-timer, a second cron (say 10:17 UTC) | no, a new runner (*guess*) | `startedToday` (`workers/night-timer/index.js:42-46`) and the `started` job (`nightly.yml:217-219`) count any timer run of the day, so both must learn a second title. GitHub keeps one *pending* run per group (`nightly.yml:129-142`) | The Worker cannot tell a drop from a 403 or a failed build without reading the bucket (a new R2 credential) or the run's verdict | kit-down (2.5 min) and preflight (6-6.5 min, logs 29 and 28 Oct) again | the bucket holds the record by then, so it needs the bucket lift machinery (§3, phase 2) |
| The workflow dispatching itself | no | as above | `actions: write` on the night job, against the least-permission rule preflight holds (`_workflows_permissions`) | as above | as above |
| A second GitHub cron line | no | as above | none | as above | as above. GitHub's cron also ran 5-7 h late on 19-24 Oct (night-timer `index.js:1-8`) |
| A person's "Re-run failed jobs" | no | gc-night | none | full | **cannot**: state-down brings the bucket's record and `gc_quiet()` defers (`nightly.py:1233-1247`) |

**Why the same process wins.**
1. **It tests the right thing.** The record calls a refusal "a fact about the ADDRESS" (`refusal.py:22-27`). A knock from the runner that met the drops asks whether *that* address is answered again.
   - A new runner, the live Worker on Cloudflare, or a cloud container would test some other address.
   - Getting through on a new address is not evidence that the block is over. It is a way round the block, and this design does not want one.
2. **Nothing can overlap it**, because there is no second run (§2.6).
3. **It needs no bucket change.** The record reaches R2 only after `nightly.py` exits (`nightly.yml:449-459`). A record lifted before then was never in the bucket, so `state_up`, `pull_refusal`, `send_refusal` and `clear-refusal`'s `cleared` never meet it. That is the readers' biggest trap (read_refusal §3), and it is avoided outright.
4. **It already has a precedent.** The try loop sleeps `EMPTY_WAIT` = 30 min under the same lock between empty exports (`nightly.py:1617-1622`, `2563-2564`). On 1-2 Oct that ran 6 passes over 3 hours and provoked no refusal (read_history §2a, incidents 9-10). Those were empty exports, not drops, so the precedent is about waiting in-job, not about drops.

**The rejected half-way design:** split the night into two workflow steps.
- "The night" would exit with a "morning" code. Step 13 would send the record to R2 at once. A new step would sleep, then run `nightly.py --runner --morning`.
- That puts the record in the bucket at once, which honours the step's own comment ("the laptop has to know at once", `nightly.yml:447-448`). But:
  - it needs phase 2's bucket lift;
  - it runs preflight a second time;
  - it splits one night's log and verdict across two processes.
- The laptop cannot act on the record before 13:30 UTC anyway (§2.6). This variant becomes worth having only once phase 2 exists, if the owner wants the record in the bucket within seconds.

---

## 2. The rules, exactly

### 2.1 Which refusals the morning may test

The morning path is taken only when **all** of these hold. The night checks them in `nightly.py` itself, from facts this process knows.
1. `--runner`, not `--dry-run` (which the ref also sets, `nightly.py:596-620`), and not `--new-term`.
2. **The schedule or the timer started the night.**
   - That means `GITHUB_EVENT_NAME == "schedule"`, or `inputs.timer` is true in the event payload (`GITHUB_EVENT_PATH`).
   - A run by hand has a person behind it, and its job may have started early enough that the arithmetic in §2.7 fails.
3. **This try met the refusal.** `archive/refused.json` did not exist when the try began (`gc_quiet()` passed), and exists now. Its `epoch` is at or after the try's `asked`.
   - So a record brought down from the bucket is never the morning's. In phase 1 it defers at `gc_quiet()` as today.
4. Its `where == "snapshot_gencourt"` and its **`kind == "dropped"`**. The kind is new (§6): the snapshot passes it at its second drop (`snapshot_gencourt.py:620-621`).
   - **A record with no `kind` is never the morning's.** That covers every one of the other note() call sites (55 in all), every record written before this change, and every fake record in preflight (`81660`, `82539`).
5. No earlier knock this run was answered. **A relapse ends the morning** (§2.4).

### 2.2 The waits, and the clock

`MORNING_WAITS = (60, 90)` minutes:
- the first knock comes 60 min after the refusal's `epoch`;
- the second comes 90 min after the first knock.

`KNOCK_MINUTES = 2` and `EXPORT_MINUTES = 40`.

Before each wait the night asks `asking_left(wait + KNOCK_MINUTES + EXPORT_MINUTES)`. It asks again at the knock, with `asking_left(KNOCK_MINUTES + EXPORT_MINUTES)`. If either says no, the knock is not made, and the log and verdict say why in `asking_left`'s own words.

**Why 60, then 90.**
- **Not seconds or a few minutes.** The founding event was a run that asked again fifty-four seconds later (`refusal.py:22-27`), and "wait a bit and try again" is what the docstring forbids (`refusal.py:35-38`).
  - Sixty minutes is 60× that gap and twice the `EMPTY_WAIT` the person already accepted.
  - The only measured web-server outage, 11 Sep, was over within 61 minutes (read_history incident 4).
  - *Guess:* a firewall's automatic short bans are commonly minutes long, so a knock an hour on is unlikely to land inside one and extend it.
- **Lengthening,** like every self-ending hold here: `probe_db`'s 20/44/92/164 h (`src/fetch/gc_db/probe_db.py:115`) and YouTube's 12 h doubling (`src/ops/livestreams.py:510-521`).
- **Two and no more.** Two knocks fit a timer night's window (below), and at most a third attempt is what was asked. A third knock would add a request to a morning that has already failed twice.

**What the clock allows.** All figures are computed from the constants, not measured.

| Refusal at (UTC) | First knock | Second knock |
|---|---|---|
| 08:27 (timer night, 29 Oct) | 09:27 (needs ≤ 10:18 ✓) | 10:57 (needs ≤ 11:18 ✓) |
| 08:48 | 09:48 ✓ | 11:18, the last minute that still fits (11:18 + 42 = 12:00, which `asking_left` refuses; 11:17 fits) |
| 09:00 (a long livestream step first) | 10:00 ✓ | 11:30 ✗: the next night (§3) |
| after 10:18 | ✗ | ✗ |
| before 08:00 (a run that early can only be by hand, so rule 2 already excludes it) | ✗: `asking_left` needs *now* inside the window | ✗ |

A night GitHub's fallback starts at 13:00-15:00 meets `asking_left`'s "outside the hours" and gets no morning. That is right: the laptop may start from 13:30.

### 2.3 The knock

**What it asks:** `GET https://gc.nh.gov/dynamicdatadump/Counties.txt`.
- It is one of the 14 the night asks for every night (`snapshot_gencourt.py:119`). It was 195 bytes on 28 Oct (that night's log, line 1697).
- It is above `MIN_BYTES = 40` (`:131`), so `read_one()`'s own test (`:333-349`) can tell a whole file from an error page.
- It is on the same path as the export that dropped.

**What it never asks:**
- the data page: opening it "rebuilds every table" and is allowed 300 s (`snapshot_gencourt.py:217-232`);
- `Docket.txt`, which is 3.2 MB;
- an invented path. Block 1 came from about a thousand of them (`probe_calendars.py:13-18`);
- netcheck's eight requests, seven of them with a browser's User-Agent (`netcheck.py:123-165`).

*Guess:* the downloads page says its tables "refresh on file access". If asking this file rebuilds it, that rebuild is ten rows.

**How it is asked:**
- with the snapshot's own User-Agent, which names the project and a contact address (`snapshot_gencourt.py:124-125`);
- through an opener with no redirect handler, so a 3xx is an answer, not a second request;
- with a 60 s socket timeout;
- killed at `KNOCK_MINUTES` by `run(timeout=seconds_left(deadline))` (nc `nightly.py:1239-1297`, `3964`).

**Where it runs:** `snapshot_gencourt.py --knock`, a child of `nightly.py`.
- It runs inside `with refusal.hold("nightly")` (`nightly.py:1574`; nc `1649`). The child is accepted as the lock holder's own (`refusal.py:350-352`).
- `--knock` is handled before `refusal.check()` (which would exit 2 at the very record it tests), as `--plan` is (`snapshot_gencourt.py:505-509`). It makes its own checks instead, and **refuses to ask** (exit 6) unless all of these hold:
  - `GITHUB_ACTIONS == "true"`;
  - the lock is its parent's (`hold()` exits 3 otherwise);
  - a record is on file with `kind == "dropped"`, `machine == "github"`, `dry == false` and no `person`.
- `_every_fetcher_checks_refusal` (`preflight.py:77647-77791`) still passes. It reads that the script calls `refusal.check()`, which the normal path still does, so no named exemption like netcheck's (`:77741`) is needed. Section 7 adds a check of the knock's own conditions in its place.

**How it is judged, and its exit codes:**

| Answer | Exit | The morning does |
|---|---|---|
| 200 with a whole data file (≥ 40 bytes, not HTML, no block page) | **0** | lifts its record and asks the export once more (§2.4) |
| dropped, reset, refused connection, timed out (`refusal.classify`, `refusal.py:295-301`); or killed at 2 min (`RUN_KILLED`, 124) | **1** | the next knock, if there is one and the clock allows; otherwise the morning ends |
| 403, 429, the block page at any status, a 3xx, or `Retry-After` on anything but a 503 | **2** | **a person's**: the record is rewritten with `kind: "refused"` and a `person` sentence, and nothing more is asked |
| 503 without the block page; 404 or 410; another 5xx; a 200 that is not a data file | **5** | the morning ends: no lift and no second knock. The server answered, but not with the file |
| the conditions above not met | **6** | nothing was asked; this is a bug, and the night says so |

### 2.4 After the knock

**Answered (exit 0).** `refusal.lift(by, answer)`:
- copies the record to `archive/refused-lifted/<UTC stamp>.json` with a `lifted` block (`utc`, `by: "the same morning's knock"`, `answer`, `run_id`);
- **then** removes `archive/refused.json`. The record is moved aside, never deleted. That is the rule `_cloud_state_and_site` holds for `clear-refusal` (`preflight.py:55341-55344`);
- the verdict's `morning` carries the whole lifted record too, and goes to `state/last-night.json`.

Then the try loop runs the snapshot again as the next try, with two limits:
- `timeout=seconds_left(...)`, counted to the knock gate's own `+ EXPORT_MINUTES` deadline;
- a new `--until <UTC>`. The snapshot starts no request within 3 min of it and installs nothing after it, so the kill is only a backstop and cannot land halfway through `install()` (`snapshot_gencourt.py:469-486`, called at `:664`, file by file).

**Why `EXPORT_MINUTES = 40`.** It is computed, not measured:
- the page's 300 s (`:232`);
- 14 files at 120 s each (`get()`'s timeout, `:277`) and up to 5 s of pause between them (`:592`);
- one 60 s retry and its 120 s.

That is about 37 min. On 28 Oct the whole export took 65 s (log line 1716).

**After that pass.** The night goes on as on any other night:
- an "empty" export goes to the database at once (`nightly.py:1587-1615`), since no refusal is on file now;
- the study views, term data, statutes and the two clock-gated web steps follow (`1626-1654`; nc `take_lsrs` and `take_documents`).

**One added limit: every later pass of the export keeps the clock.** If that pass comes back empty and the database cannot be used, the loop's 30-minute retry (`TRIES_AFTER_DB`, `2612`) is asked only if `asking_left(EXPORT_MINUTES)` allows it. Otherwise it is "not asked for". This keeps all of the morning's asking before 12:00.

**Relapse.** If that pass is dropped twice again, the snapshot writes a new record and **the morning ends**: no further knock, even if the clock would allow one.
- Two answered connections, then two dropped ones, say the trouble is not the connection's.
- A third pass of the page in one morning against a server that just dropped it twice is the "try again" the rule exists to stop.
- The new record carries `relapse_of` (the lifted copy's name).

**Not answered (exit 1)** after the last knock the clock allows, **or exit 5:**
- the record is rewritten with `morning: [{utc, answer, rc}, ...]` and `morning_ended: "<why>"`. That is safe because it has not been sent: its sha256 is first computed at `state-up`;
- `nightly.py` ends as today: "REFUSED while fetching." at the start of a line, so preflight's `NIGHTLY_WHY` still names it (`preflight.py:81707-81715`);
- step 13 sends the record (`nightly.yml:449-459`).

**Exit 2 (a person's).** The record's `kind` becomes `"refused"`, with `person: "the knock at 09:27 UTC was answered by <...>"`. Nothing more is asked, by the morning or by phase 2's ladder.

**While waiting.** The night sleeps in slices of at most 15 minutes. Each slice ends with a `say()` line printed to GitHub's log too (`nightly.py:1145-1150`), for example "waiting for the knock at 09:27 UTC (2 of 2 at most); nothing is asked meanwhile". A step silent for an hour would look like a hang ("Silence is not success", CLAUDE.md).

The lock's heartbeat keeps `archive/.lock` fresh throughout (`refusal.py:361-370`).

### 2.5 503, decided

**The decision:**

| Answer | On the night's own pass | On a knock |
|---|---|---|
| **503 without the block page** | Still stops the run at once (`classify()` unchanged, `refusal.py:286`). Recorded as `kind: "unavailable"`. **Never the morning's.** Phase 1: a person's. Phase 2: the ladder, never before its `Retry-After` | exit 5: ends the morning, never a lift |
| **429** | a person's | a person's |
| **403** | a person's | a person's |
| **the block page** | a person's | a person's |

**Why a 503 never gets the same morning:**
1. **No 503 from gc.nh.gov has ever been recorded** (read_history §3B). There is nothing to tune a same-morning wait on.
2. **A 503 is the server answering.** The connection is not the trouble. The server said "not now", and `classify`'s own comment reads it as "a request to go away, not a flaky link" (`refusal.py:261-263`). Asking again within hours of that is the most literal "wait a bit and try again".
3. **The morning exists for the one shape actually seen,** two drops after a quiet day (29 Oct). The cost of being wrong about drops is bounded by drops' own two-strike rule.
4. **A 503 is not a block either.** *Guess:* IIS answers 503 when an application pool is stopped, which is maintenance. So it should not be a person's for ever. Phase 2's ladder, at a day or more and honouring `Retry-After`, is the right size for maintenance.

**429 stays a person's:** it is a complaint about our rate, aimed at us.

**`classify()` does not change,** so the 503 cases in `_every_fetcher_notes_refusal` (`preflight.py:77970-77974`) stay green. The new `refusal.record_kind()` reads the status and the body only to label the record.

### 2.6 One fetch at a time

**Against the first run.** There is no second run. The knock and the extra pass are the same process:
- under the same `archive/.lock` (`refusal.hold("nightly")`);
- in the same `night` job, in group `gc-night`, which keeps every other night or weekly job waiting (`nightly.yml:244-248`; weekly `weekly.yml:100-102`).

**Against the laptop.** A stood-down laptop starts no General Court request:
- inside 08:00-13:30 UTC or in the 30 minutes before (`refusal.py:520-533`, `gc_turn` `707-729`);
- after 13:30 until it has read the real bucket since the window closed (`730-743`).

Every morning request ends before 12:00 (`asking_left`), and the night exits by about 12:55 at worst (§2.7). Any record still standing is then in the bucket before 13:30, and the laptop reads it at its next required pull. The night-clock branch already relies on this ("a refusal the night meets reaches the bucket only when this exits", nc `nightly.py:466-468`, `716-720`).

**Against the live Worker** (designed, not built). It never asks gc.nh.gov (`wf16/design_final.md` §0). Its heartbeat and warm reads of the SQL host "never start inside a window" (`design_final.md:374`).

**Against runs started by hand.**
- A dry run or a run by hand of main waits in `gc-night` until the morning's job ends, then reads whatever step 13 sent.
- The already-open caveat (`nightly.yml:139-142`) grows: GitHub keeps one *pending* run per group, so two runs started by hand during a long morning can cancel one another. The main night is never pending in that queue.

**Against netcheck.** netcheck is outside every guard (read_refusal §2). A person who runs it from the laptop between 08:00 and 12:00 would be a second machine asking beside the night. That is already true today.

### 2.7 The job's limits

The `night` job allows **300 min** (`nightly.yml:234`).

A morning night is always a scheduled or timer night (§2.1, rule 2). Its job starts at **08:17 UTC or later** (`wrangler.toml:11`; GitHub's cron never starts early), so the limit falls at **13:17 or later**.

All morning asking ends before 12:00. After the export, the night takes about 45 min on the measured night (28 Oct log):
- the database steps, about 8 min (term data 412 s);
- the build, 1,813 s;
- the built checks, 372 s;
- reports and gates, about 1 min.

The workflow's tail after `nightly.py`, when nothing was built, took 48 s on 29 Oct (read_night §2). The preview and the pack add a few minutes (*guess*).

**Worst case:** a second-knock pass that runs its full 40 min to 11:59, then 45 min, then about 10 min of tail, ends at about **12:55**. That is 22 min inside 13:17, and 35 min before 13:30.

A new constant, `MORNING_AFTER_MINUTES = 60`, carries that allowance. preflight holds `ASK_UNTIL + MORNING_AFTER_MINUTES ≤ the timer's 08:17 + timeout-minutes` (§7, check F).

**The Healthchecks catch (a guess).** From Healthchecks' documentation as I remember it, not checked here: a check that got `/start` (`nightly.yml:267-286`) and no completion within its grace time goes down. A morning night can run about 4.5 h after `/start`, against about 1 h today. The grace time is set in Healthchecks, not in the repository. The owner should set it to at least 5 h, or a recovering morning will send a false "down" email.

---

## 3. The next night, if the morning never recovers

**The record that reaches the bucket** at the end of a failed morning (29 Oct, both knocks dropped):

```json
{"at": "2026-10-29T04:27:14", "epoch": 1793262435.0, "where": "snapshot_gencourt",
 "why": "RemoteDisconnected: Remote end closed connection without response",
 "kind": "dropped", "machine": "github", "dry": false, "run_id": "40841071509", "attempt": "1",
 "answers": ["page: dropped: RemoteDisconnected", "Docket.txt: dropped: RemoteDisconnected"],
 "morning": [{"utc": "2026-10-29T09:27:15Z", "rc": 1, "answer": "dropped: RemoteDisconnected"},
             {"utc": "2026-10-29T10:57:20Z", "rc": 1, "answer": "dropped: RemoteDisconnected"}],
 "morning_ended": "two knocks, neither answered"}
```

The figures are illustrative. `at` is the runner's Eastern clock, and `epoch` is true UTC (read_night §0).

**Phase 1, the morning alone.**
- The next night does what it does today. `gc_quiet()` finds the record and defers (`nightly.py:1233-1247`, `1554-1557`).
- The person clears it with `netcheck.py`, then `cloud.py clear-refusal` and `refusal.py --clear`.
- Two things change:
  - the alert says what the morning tried (§5);
  - an outage up to about 2.5 h after a timer night's refusal no longer costs any day at all.

**Phase 2, the ladder.** This is the next-night design in `design_minimal.md` §2-§5, unchanged except for how the morning feeds it.
- **Who may be tested:** a record with `kind` in `("dropped", "unavailable")`, `machine == "github"`, `dry == false` and no `person`.
- **When:** `KNOCK_HOURS = (16, 40, 88, 160)` counted from the last request that failed. That is the last morning knock, when there was one.
  - From 10:57, 16 h is 02:57, so the next timer night (about 08:27) is always due.
  - A 503's `Retry-After` is honoured.
- **How often:** one knock a night, at the night's start, inside `gc_quiet()`'s new order:
  1. a person's record defers;
  2. a record not yet due defers, saying when;
  3. a due record knocks under the lock, before the export.
- **No morning extras on a ladder night.** A ladder knock that fails waits for the next rung. A night that lifted at its start and then relapses goes to the next rung. Two knocks a morning are only for the night that met the drops fresh. Once a blip has outlasted a morning, it is an outage measured in days, and `probe_db`'s "one connection a night" is the right size (`probe_db.py:86-89`).
- **When it becomes a person's:** after `KNOCKS_MOST = 4` failed ladder knocks, or on any refused-kind answer.
- **The lift must reach the bucket:**
  - `archive/knocks.json` becomes R2's `state/knocks.json`;
  - `cloud.lift_refusal()` runs at the top of `state_up` on main's real night and moves `state/refused.json` to `replaced/<day>/`;
  - `pull_refusal` and `send_refusal` read `knocks.json`, so the laptop neither fails its pull nor sends the refusal back (read_refusal §3, `cloud.py:2801-2807`, `2168-2174`);
  - `knocks.json` joins `DRY_NEVER`.
- **`fetch_committees`** passes a kind too, so a Monday weekly's drops at about 04:20 are tested by Monday's night. Under phase 1 they stop the night until a person acts, as today. That is a gap only phase 2 closes.

**Requests one outage can cost** before it is a person's:

| | Phase 1 | Phase 2 |
|---|---|---|
| The two drops | 2 | 2 |
| Morning knocks | ≤ 2 | ≤ 2 |
| Ladder knocks | 0 | ≤ 4, on 30 Oct, 1, 5 and 12 Nov for a 29 Oct refusal |
| **Single requests to a server that may be blocking** | **≤ 4 in one morning** | **≤ 8 over 14 days** |
| Export passes | only after an answered knock, one per answer, each under the snapshot's own two-drop stop-loss | the same |

For comparison, block 1 was about 1,000 requests for missing files (`probe_calendars.py:15-16`).

---

## 4. 29 October under this design

Times are UTC. Facts come from the log and the readers. The rest is computed from the constants.

| When | What |
|---|---|
| 08:17:24 | Run 151 is created by the timer (`workflow_dispatch`, `inputs.timer`). |
| 08:21:13-08:27:08 | preflight, 356 s. |
| 08:27:08-15 | The page is dropped, then `Docket.txt` is dropped. `note(kind="dropped")` writes the record. The snapshot exits 2. |
| 08:27:15 | The morning path's conditions hold (§2.1). `asking_left(60+2+40)` gives a deadline of 10:09:15, which is ✓. The log says "the day's files were refused at 08:27 UTC: two connections closed without an answer. One request at 09:27 UTC will say whether the site answers again; nothing is asked before then." |
| 08:42, 08:57, 09:12 | A waiting line each in GitHub's log. |
| **09:27:15** | `asking_left(42)` ✓. Knock: `GET .../Counties.txt`. |
| ↳ answered | The record is lifted (moved aside). Try 2 runs: about 65 s on 28 Oct's evidence. Then the database steps, the bill requests (clock ✓), the lists (clock ✓), the build and the checks; `nightly.py` exits at about 10:15. Preview, pack, kit-up, verdict, state-up. The publish job goes through `production`, because the morning's warning never holds the gate (§5). **Live at about 10:25 UTC (06:25 EDT)**, against about 09:25 on an ordinary night. |
| ↳ dropped | `asking_left(90+42)` gives 11:39:20, ✓. Wait. |
| **10:57:20** | The second knock. |
| ↳ answered | As above. **Live at about 11:55 UTC (07:55 EDT).** |
| ↳ dropped | The record gets `morning` and `morning_ended`. "REFUSED while fetching." `nightly.py` exits at about 10:57:30, and step 13 sends the record. One Healthchecks email names both knocks. The site stays at 28 Oct's build. |
| 30 Oct | Phase 1: deferred, a person's. Phase 2: one knock at about 08:27 (16 h after 10:57 has passed). |

**The standing record is not covered.** It was written before this change and carries no `kind`. Clearing it now is the owner's call, as it is today. `netcheck.py`'s last line counts any HTTP status as "got through", a 403 included (`netcheck.py:162`, `196-198`), so read its printed table.

---

## 5. What the person sees

**The verdict** (`archive/last-night.json`, then `state/last-night.json`) gets `"morning"`:

```json
{"refused_at": "08:27 UTC", "kind": "dropped",
 "knocks": [{"utc": "09:27 UTC", "answer": "answered: Counties.txt, 195 bytes"}],
 "lifted": {"...": "the whole record"}, "ended": null}
```

`tried` reads `["the export, try 1: refused (two connections dropped)", "the knock at 09:27 UTC: answered", "the export, try 2: installed"]`.

**A recovered morning** is a **warning**, `KIND_MORNING`:
> "The day's files were refused at 08:27 UTC: two connections closed without an answer. One request at 09:27 UTC was answered, and the files were asked for again and arrived whole."

- Where it shows: on the run's page; in `warns_of()`, so the warnings' check gets `/fail` and the person an email if that check was up (`nightly.yml:597-616`).
- **It never holds the gate.** `warning_reasons` would otherwise hold any new kind (`nightly.py:4819-4844`), so `morning_kind()` is exempt there exactly as nc's `clock_kind()` is (nc `3972`).
- The night's own check stays up, because the night was clean.
- Every sentence is the project's own words. Warnings are public (`nightly.py` `take_documents`' docstring).
- **Owner's option:** count recovered mornings in the last 7 verdicts, and at 3 put the line in `alerts_of()` instead, so a server that drops every morning is not just a warning.

**A failed morning** keeps today's `/fail`, with these words in `alerts_of()` (`nightly.py:5758-5763`), `plain_why()` (`2283-2285`) and `1704-1706`:
- **Phase 1:**
  > "The General Court closed two connections without answering at 08:27 UTC. The night asked once more at 09:27 and at 10:57 UTC, one request each, and neither was answered, so nothing was taken or published. Every fetch now waits until a person clears it: python3 netcheck.py says what kind it was, then python3 src/ops/cloud.py clear-refusal."
- **Phase 2:** the same, ending:
  > "The next night asks once, one request, from about 08:27 UTC on 30 October; if that is not answered, again on 1, 5 and 12 November, and then it waits for you. To lift it sooner: ..."

**A knock answered by a block (exit 2):**
> "The General Court's firewall answered the night's one request at 09:27 UTC with its block page. Nothing more is asked; this is a person's to clear."

The same line goes to `warns_of()` too, because the night's check is already down by then (read_night §1.7).

---

## 6. Code changes, file by file

### Phase 1, the morning alone

**`refusal.py`** (`2026-09-09.19` becomes `.20`)
- `note(where, why, kind=None, **extra)` (`:113-127`). With a kind it adds:
  - `kind`;
  - `machine` (`"github"` when `GITHUB_ACTIONS == "true"`, else `"laptop"`);
  - `dry` (`DRY_RUN == "true"` or `GITHUB_REF != "refs/heads/main"`);
  - `run_id` and `attempt`;
  - any `extra` (for example `answers`).

  Without a kind, the record keeps today's four fields.
- `record_kind(err=None, body=None)`:
  - `"dropped"` where `classify` says dropped;
  - `"unavailable"` for an HTTP 503 whose body is not the block page;
  - `"refused"` for everything else `classify` calls refused.

  `classify` itself is untouched.
- `morning_may(d)`: the record-side half of §2.1 (kind dropped, github, not dry, no `person`). `--knock` reads it.
- `lift(by, answer)`: moves the record to `archive/refused-lifted/<stamp>.json` with `lifted`, then removes `MARK`. It never deletes the copy.
- `to_person(why)`: rewrites `MARK` with `kind: "refused"` and `person`.
- The docstring's HOW IT BEHAVES (`:31-38`) gets a THE SAME MORNING paragraph.
- `force()` (`:195-208`) and `main()`'s status line (`:861-863`, already wrong for the night and the lane) are corrected.

**`src/fetch/gc_web/snapshot_gencourt.py`**
- The three `note()` calls pass a kind:
  - `:585`, the block page on the page: `"refused"`;
  - `:615`, a refused file: `record_kind(...)`. `read_one()` (`:333-349`) returns the status code with its kind, so a 503 is told from a 403;
  - `:621`, the second drop: `"dropped"`, with `answers` naming both.
- `knock()`, behind `--knock`:
  - handled before `refusal.check()`, as `--plan` is (`:505`);
  - one request, no redirect, its own preconditions, exit codes 0/1/2/5/6 (§2.3);
  - writes `archive/knock.json` (`utc`, `url`, `rc`, `answer`), which nightly reads.
- `--until <UTC>`: no request starts in the last 3 min before it, and no install happens after it.
- `:683`: "holds every fetch for a day" is wrong for the night. It becomes "is recorded; the night that met it may test it the same morning (nightly.py, THE SAME MORNING), and otherwise it waits for a person".

**`nightly.py`**
- Constants: `MORNING_WAITS = (60, 90)`, `KNOCK_MINUTES = 2`, `EXPORT_MINUTES = 40`, `MORNING_AFTER_MINUTES = 60`.
- `scheduled_night()`: `GITHUB_EVENT_NAME` and the event payload's `inputs.timer`.
- `again_this_morning(a, night, asked)`:
  - checks §2.1;
  - then for each wait: `asking_left`, sleep in slices, `asking_left` again, then `run(["snapshot_gencourt.py", "--knock"], ..., timeout=seconds_left(...))`;
  - acts on the exit code (§2.3-2.4);
  - returns the export deadline on a lift, or None.
- **The hook,** in the try loop: right after `night.v["tried"].append(...)` and before the break at `1587-1589` (nc `1662`):

  ```python
  if got == "refused" and night and not night.v.get("morning_lifted"):
      until = again_this_morning(a, night, asked)
      if until:
          export_until = until          # the next try runs with timeout= and --until
          last = max(last, tries + 1)
          continue
  ```

  The `run([... "snapshot_gencourt.py" ...])` call at `1576-1578` takes `timeout=` and `--until` when `export_until` is set. The `EMPTY_WAIT` retry after it keeps the clock (§2.4).
- `KIND_MORNING`, `morning_kind()` exempt in `warning_reasons` beside `clock_kind`, the warning in `warned()`, and the line in `warns_of()`.
- The texts:
  - the sentence at `1704-1706`;
  - `plain_why` `2283-2285`;
  - `alerts_of` `5758-5763`.
- The docstring:
  - "IT ASKS ONLY WHEN NOTHING ELSE IS ASKING" (`26-30`) gains "except the one refusal tonight's own snapshot met, which THE SAME MORNING tests";
  - a new THE SAME MORNING section;
  - nc THE NIGHT'S CLOCK's last sentences: "The day's files keep their own rule ... once whenever it runs; only the same morning's knocks, and the export passes they earn, keep these hours".

**`.github/workflows/nightly.yml`: comments only, no logic.**
- Step 13's "at once" (`447-448`) becomes "as soon as the night has finished with it: the same morning's knocks come first, all before 12:00 UTC, and the laptop is held until 13:30".
- The paragraph above the night step (`420-436`), which explains the 300 minutes, names the morning.
- preflight reads some of these comments, so the changed sentences go with their checks.

**`preflight.py`** (§7) and **`versions.json`:** every stamp bumped (`src/ops/inventory.py --bump-changed`).

### Phase 2, the ladder (summary; `design_minimal.md` §8 has it file by file)

- `refusal.py`: `KNOCK_HOURS`, `KNOCKS_MOST`, `whose(d, k)`, and `knocks.json`.
- `nightly.gc_quiet()`'s new order, with the lock taken before it.
- The weekly's `gc_quiet` (`5981`).
- `fetch_committees.py`'s kind.
- `cloud.py`: `lift_refusal` in `state_up`; `pull_refusal` and `send_refusal` read `state/knocks.json`; `DRY_NEVER`.
- `cloud_kit.json`'s state entry, and the refused.json `what`.
- The phase-1 `morning` field feeds the first rung.

---

## 7. The checks. Each fails if its rule is removed

### New

**A. `_refusal_records_kind`** (refusal alone, a temporary `MARK`)
- `note(..., kind="dropped")` with `GITHUB_ACTIONS=true`, `DRY_RUN=false` and `GITHUB_REF=refs/heads/main` writes `kind`, `machine: "github"`, `dry: false` and `run_id`.
  - `DRY_RUN=true` gives `dry: true`. **Fails if `dry` ignores the box.**
  - `GITHUB_REF=refs/heads/dev` gives `dry: true`. **Fails if it ignores the ref.**
  - With no `GITHUB_ACTIONS`, `machine: "laptop"`.
- `note(where, why)` writes exactly the four old keys. **Fails if a kind is invented for the 55 sites that pass none.**
- `record_kind`:
  - HTTPError 503 gives `"unavailable"`;
  - a 503 whose body is the block page gives `"refused"`;
  - 403 and 429 give `"refused"`;
  - `RemoteDisconnected` gives `"dropped"`.
- `morning_may` is false for each of: no kind, `refused`, `unavailable`, `laptop`, `dry`, and `person`. **Each case fails if its condition is dropped.**
- `lift()` leaves the old bytes, with `lifted` added, under `refused-lifted/`, and no `MARK`. **Fails if `lift` deletes.**

**B. `_snapshot_stops` gains rows** (it already drives `SG.run`, `preflight.py:81515-81636`)
- A dropped page, then a dropped `Docket.txt`: rc 2, 2 requests, the record's `kind == "dropped"` and `answers` naming both. **Fails if the kind is not passed at `:621`.**
- A 403 gives `kind == "refused"`, and a block-page body gives `"refused"`. A 503 gives `"unavailable"`. **Fails if `:615` passes one word for all.**
- `--until` in the past: no request is made and nothing is installed.

**C. `_snapshot_knock`** (`SG.knock()` through `main()`, with a faked opener)
- A whole `Counties.txt`: exit 0, **exactly 1 request**, its URL `BASE + "Counties.txt"`, never `PAGE`, and the header `SG.UA`. **Fails if the knock asks the page, another file, or twice.**
- `RemoteDisconnected` gives 1, and a timeout gives 1.
- 403, 429 and a 200 block page each give 2.
- **A 302 gives 2 with exactly 1 request.** **Fails if a redirect is followed.**
- 503, 404 and a 200 HTML page each give 5.
- **It refuses before any request** (exit 6) in each of these cases. **Each fails if its precondition is dropped.**
  - with no `GITHUB_ACTIONS`;
  - with no record;
  - with a record with no kind;
  - with `kind: "refused"`;
  - with `dry: true`.
- With the lock held by another pid it gives 3.

**D. `_nightly_morning`** (drives `nightly.py --runner` through `main()` as `_nightly_runner` does, `preflight.py:82273`; `GRANITE_CLOCK_UTC` set; a fake `NI.time.sleep` that moves the clock on)
1. 08:27, `GITHUB_EVENT_NAME=schedule`. Try 1 writes a dropped-kind record and exits 2; the knock gives 0; try 2 installs.
   - Asserts:
     - the calls run snapshot, knock, snapshot, in that order;
     - the knock came at least 3,600 s after the record's epoch;
     - the verdict reads `fetch: installed`, clean, with `morning.knocks` of length 1;
     - no `MARK`, and the lifted copy is equal to the record plus `lifted`;
     - try 2 got a `timeout` and `--until` at or before the gate's deadline;
     - the log has no line starting "REFUSED while fetching";
     - `warning_reasons` gives nothing for `KIND_MORNING`.
   - **Fails if:** the wait shrinks; the knock is skipped; the lift deletes; the extra pass runs unbounded; or the warning holds the gate.
2. Knock 1, then 0. The second knock is at least 5,400 s after the first. **Fails if the second wait shrinks.**
3. Knock 1, then 1: exactly **two** knocks, exit 1, and the record has `morning` (2 entries) and `morning_ended`. The log has "REFUSED while fetching", and the alert names both times. **Fails if a third knock is made.**
4. Knock 2: one knock, the record `kind: "refused"` with `person`, and nothing more asked.
5. Knock 5: one knock, and no second.
6. Relapse: knock 0, then try 2 drops twice. **No further knock.** **Fails if a relapse earns a knock.**
7. Try 1's record has `kind: "refused"`: no knock. A record with no kind (today's shape, `where: snapshot_gencourt`): no knock. **Fails if the path keys on `where` or on any `refused`.**
8. `--dry-run`: no knock. `--new-term`: no knock. `GITHUB_EVENT_NAME=workflow_dispatch` with no timer input: no knock. **With `inputs.timer: "true"`: a knock.**
9. **The clock:**
   - refused at 10:30: no knock, and the line begins "it is 10:30 UTC";
   - refused at 09:00 with knock 1 failing: no second knock;
   - refused at 07:55: no knock.

   **Fails if `asking_left` is removed.**
10. A dropped-kind record already on file when the night starts (brought down from the bucket): `FETCH DEFERRED`, with no knock and no snapshot. **Fails if the morning reads a record it did not meet** (phase 1; phase 2 rewrites this case to the ladder's).
11. An empty export after the lift, the database unusable, at 11:35: the `EMPTY_WAIT` retry is "not asked for". **Fails if a later pass escapes the clock.**

**E. `_night_clock`** (nc `preflight.py:92277`) **changes.**
- `gated == ["again_this_morning", "take_documents", "take_lsrs"]` (`:92374`).
- The docstring regex at `:92379` follows the new sentence.
- It already fails if a gate is removed.

**F. A job-limit sum.** In `_workflows_*`, beside the livestream step's sum: `ASK_UNTIL + MORNING_AFTER_MINUTES ≤ 08:17 + the night job's timeout-minutes`, reading the cron from `wrangler.toml`. **Fails if `ASK_UNTIL` moves past 12:17 or the job's limit drops below 283 min.** Also `EXPORT_MINUTES*60 ≥ PAGE_TIMEOUT + len(targets()) × (120 + 1.25 × default delay) + 60 + 120`, read from the snapshot's constants. **Fails if a timeout grows past the allowance.**

**G. `_nightly_guards`** (`preflight.py:81641`) **gains an AST assertion.** `again_this_morning(` is called only inside the `with refusal.hold(...)` block. **Fails if the knock leaves the lock.**

### Unchanged, and why they stay green

| Check | Why it stays green |
|---|---|
| `_nightly_guards`' old record (`81660-81661`) and `_nightly_runner`'s fake record (`82539-82546`) | neither has a `kind`, so both still defer |
| `_nightly_falls_back` runs 310, 311, 314 and 317 (`90012-90130`) | the morning uses no database while a record stands. Run 317's refusal comes in an "empty" pass, not a "refused" one |
| `_every_fetcher_checks_refusal` | still sees `refusal.check()` in the snapshot |
| `_every_fetcher_notes_refusal` | `classify` is unchanged |
| `_cloud_state_and_site`, `_cloud_pull`, and the lane | nothing in the bucket or on the laptop changes in phase 1 |
| `_night_window` | the window is unchanged |
| `_ls_hold` | unrelated |

---

## 8. Docs, and the CLAUDE.md sentence

**Docs that change with phase 1:**
- `refusal.py:31-38`, `195-208`, `861-863`.
- `nightly.py:26-30`, the new section, nc `447-468`, `1704-1706`, `2283-2285`, `5758-5763`.
- `snapshot_gencourt.py:683`, and its docstring for `--knock` and `--until`.
- `nightly.yml:447-448`, and the paragraph above the night step (`420-436`).
- `ARCHITECTURE.md`:
  - the night's paragraph (`113-117`; nc adds the clock there): "...the day's bulk files, asked only when no refusal is on file -- and, where the night's own snapshot had two connections dropped, asked again later the same morning after one answered request (THE SAME MORNING)...";
  - `266-272`: "a refusal held for three nights is one email and its recovery is the sign it was cleared" becomes "... the sign it was cleared or, in phase 2, tested and lifted by the night".
- `CONTRIBUTING.md:24-31` and `README.md:344-353`: one clause each: "except that GitHub's scheduled night tests two dropped connections it met itself, with one request an hour later and once more ninety minutes after, before 12:00 UTC".
- `SECURITY.md:93-98`: "and the nightly do not ask while one is on file" gains "but for the one request the night that met a dropped connection makes to test it".
- **Phase 2** also changes `cloud_kit.json`'s refused.json `what`, `watchers/README.md:71-83`, and `cloud.py:230-242`, `2057`.

**CLAUDE.md is the owner's to edit.** Proposed replacement for lines 74-79. It also corrects two things the readers found already wrong there: the lane is held at any age, not 24 h; and the docstring says fifty-four seconds, not twelve.

> **A refusal outlives the run that met it.** `refusal.py` records one in
> `archive/refused.json`. It exists because a drain that met two 403s stopped
> itself correctly, and a chained run started asking the same address
> fifty-four seconds later. A fetch started by hand stops at it for 24 hours;
> the lane stops at it for as long as it is on file. Clearing it is a person's
> decision -- `python3 refusal.py --clear`, and `python3 src/ops/cloud.py
> clear-refusal` for the bucket's copy, after `netcheck.py` has said what kind
> of refusal it was -- with one exception the person approved on <date>: when
> GitHub's scheduled night has two of its own connections closed without an
> answer (`"kind": "dropped"`), it asks once more, one request for
> `Counties.txt`, an hour later, and once more ninety minutes after that, under
> its own lock and only where that request and the export after it end before
> 12:00 UTC; an answer lifts the refusal (moved aside, never deleted) and the
> night goes on. [Phase 2: A refusal the morning did not lift is tested once a
> night on the ladder in `refusal.py`, and then is a person's.] A 403, a 429,
> the firewall's block page, a redirect, any refusal met on the laptop, by a
> dry run or by a run started by hand, and any record without a `kind`, stay a
> person's.

---

## 9. Risks

1. **A real block looks the same on the wire.** 29 October's answer cannot be told from the repository's only first-hand description of a block (`netcheck.py:13-19`).
   - A blocked address takes up to 2 more single requests in 2.5 h, plus 2 to 4 on the ladder in phase 2. Block 1 was about 1,000 requests.
   - *Guess:* a firewall that blocked a directory scan does not lengthen a block for one request an hour. Nothing in the repository shows how it treats one.
2. **The same-address assumption.** That the job's runner keeps one outbound address for its life is a *guess*: no log records the address. If it changed mid-job, the knock would test another address, and the lift would rest on that answer.
3. **The bucket learns of a refusal later.** On a failed morning it arrives at about 11:00 instead of 08:27; on a relapse, by about 12:55.
   - The laptop cannot act on it before 13:30, so this costs nothing there.
   - If the runner dies mid-wait, step 13 never runs and the record is lost with the machine. The next night then asks the export as normal, and stops again after at most two more drops (2 requests, 24 h later). Healthchecks' dead-man's switch reports the dead night.
   - The two-step variant (§1) closes this, at phase 2's cost.
4. **Long jobs.**
   - A Windows runner can sit idle for up to about 2.5 h. Its cost is not established (*guess*: free if the repository is public).
   - `gc-night` is held up to about 4.5 h instead of about 1 h, so runs started by hand wait behind it, and two of them can cancel one another while pending (`nightly.yml:139-142`).
   - Healthchecks' grace time (§2.7) is a *guess* and the owner's to set.
5. **A kill mid-install.** `--until` makes the kill a backstop only (§2.4). If `--until` were dropped, a kill during `install()`'s file-by-file writes could leave files from two days. Check B holds `--until`.
6. **Hiding a pattern.** A server that drops every morning's first two requests would publish an hour late every day, with a warning each time. The owner's option in §5 (3 in 7 becomes an alert) addresses it.
7. **The knock itself.**
   - It is answered, but the export relapses. The morning then ends with a new record, so the ceiling holds.
   - `Counties.txt` could someday be removed. Exit 5 then ends every morning without a lift, and the alert names the 404.
   - *Guess:* whether asking `Counties.txt` rebuilds anything is unknown.
8. **No dry run can prove it.** By rule, a dry run never knocks. The proof before production is check D on fakes; the first real proof is the next real drop.
   - *Optional:* a `tests/rehearse_morning.py` against a loopback server. That needs the snapshot's `BASE` overridable for tests only, which is a new way to point a fetcher elsewhere and should be preflight-only.
9. **The night-clock merge is a prerequisite.** This cannot ship before `feat/night-clock` is on main (early November). A drop in between costs a person, as now.
10. **The approval gate still applies after a recovery.** A recovered night is an ordinary export night. A release older than its 48-hour dry-run proof, or more than 600 rows changed, still holds it (read_holds §3.2). The morning does not touch that.

---

## 10. The owner's idea, weighed from the morning

> "the live updates may assist in that regard since presumably they'd be more frequent and lightweight pings that the nightly can resume whenever the live shows it's up again"

**As the signal that ends a morning's wait, it cannot work:**
1. **It never asks the web server that dropped.** The live Worker reads PublicSQL and YouTube, and "ask gc.nh.gov" is under what it never does (`design_final.md` §0). A healthy database proves nothing about `gc.nh.gov`, and 29 Oct's drops were the web server's.
2. **It is deliberately silent during the morning.** Its heartbeat and warm reads "never start inside a window" (`design_final.md:374`). The only exception is a sitting already live on stream. Off-season it reads nothing at all outside 1 January to 30 June (`:345`). On 29 October, from 08:27 to 12:00, it would have said nothing.
3. **It would answer for the wrong machine.** It runs from Cloudflare's addresses, and its success says nothing about the runner's.
4. **A gc.nh.gov ping from the Worker would be a second machine asking inside the night's window.** That is what `NIGHT_WINDOWS` exists to prevent, and two at once is how the second block happened (`refusal.py:312-316`).
5. **The night cannot read the Worker's bucket.** It holds only the kit bucket's credentials (`nightly.yml:334-337`).

**Where the idea is right, and is taken:**
- **Its shape is this design.** "Frequent, lightweight pings, and resume when one shows it is up" is exactly the morning's knock. It is one 195-byte request, and an answer resumes the night at once. It just has to come from the machine that will fetch, inside the night's own lock, so that a ping cannot become a second worker.
- **On a session morning the live layer softens the wait.** While the night waits, Live Now and the live votes keep the session-day page current from PublicSQL (`design_final.md` §4.2), so a two-hour wait costs readers less on exactly the days it matters most.
- **January to June, it is evidence for the person.** A heartbeat answering after 09:30 EDT on a morning the night failed says the General Court's systems are up and the trouble is the web server's. That supports "outage, not block" when the person decides about phase 1's leftover record. It is evidence, not a trigger.
- **The database door is compatible with the morning, and the two add up.** If the owner approves the database as the night's source while a dropped-kind record stands (`design_fresh.md`), it would fill the day at about 08:28. The morning's export, if a knock is answered, would then install the website's files over it, with Members.txt and the six lookups the database lacks (`nightly.py:2603-2606`). This design does not depend on that.

---

## 11. Decisions for the owner

1. **Approve the same-morning exception.** Only two dropped connections; only on a scheduled or timer night; from the night's own runner and lock; at most two single requests and one extra export pass; all before 12:00 UTC. This changes "Nothing clears it automatically" (`refusal.py:35-38`), and it is a change only the owner can approve.
2. **The waits:** 60 then 90 min (recommended), or other numbers. A first wait shorter than 30 min is not recommended (§2.2).
3. **A relapse ends the morning** (recommended), or a relapse may still use the second knock.
4. **503:** never the same morning. Under phase 1 it is a person's; under phase 2 it is on the ladder after `Retry-After` (recommended). Or 503 stays a person's in both.
5. **Phase 2 or not.** Without it, a refusal the morning cannot lift is a person's, as today. With it, the next nights test it on 16/40/88/160 h and then hand it over. Phase 2 is what an unattended month needs. Phase 1 alone covers outages up to about 2.5 h.
6. **A recovered night publishes itself** (recommended; its warning is exempt from the gate), or it waits for approval the first few times.
7. **Optional:** recovered mornings 3 in 7 become an alert.
8. **The Healthchecks night check's grace time:** set it to at least 5 h (§2.7).
9. **The knock's file:** `Counties.txt` (recommended), or `Members.txt` on `/downloads/`.
10. **The 29 October record** has no kind and stays a person's. Clear it now, after reading netcheck's printed table, if satisfied.
11. **The CLAUDE.md paragraph in §8,** and whether to fix its two errors in the same edit.

---

## 12. Effort (a guess)

**Phase 1:** about 1 to 1.5 days of agent work, plus one review round.
- Code changes: `refusal.py` about 60 lines, `snapshot_gencourt.py` about 90, `nightly.py` about 150, plus docstrings.
- Checks: A to G, about 450 lines of preflight, most of it check D on `_nightly_runner`'s fakes.
- Docs.

It is built after `feat/night-clock` merges. No workflow logic, bucket, laptop or Worker change.

**Phase 2:** about 2 more days. Most of it is `cloud.py`'s lift and the laptop's pull and send.

---

## 13. Said plainly as guesses

- A GitHub runner keeps one outbound address for the job's life, and a new runner gets another. No log records either.
- Whether either 29 October knock would have been answered. The only evidence is one unlogged netcheck from another machine about 8 h later, and netcheck counts a 403 as "got through".
- How the General Court's firewall treats one request an hour after it dropped two. No block has a recorded wire answer, length or trigger beyond the two the project provoked.
- That asking `Counties.txt` rebuilds at most ten rows.
- Healthchecks' behaviour on a long run after `/start`, and the night check's grace time.
- The cost of idle runner minutes, which depends on whether the repository is public. Not checked.
- That IIS's 503 means maintenance.
- Post-fetch duration (about 45 min) and the export's 65 s are one night's measurements (28 Oct). `EXPORT_MINUTES`' 37 min worst case is arithmetic.

## 14. Notes on the readers' findings

- Confirmed in the code:
  - the two-drop path (`snapshot_gencourt.py:581-630`);
  - the record's four fields (`refusal.py:113-127`);
  - the loop's break (`nightly.py:1587-1589`);
  - `asking_left` requiring *now* inside the window (nc `3946-3955`).

  The last one is why a refusal before 08:00 never knocks.
- The night-clock tip is now `22d19e4`, not `84a81ee`. The extra commits are a merge of dev and stamps. The line numbers above are `22d19e4`'s.
- The 28 October log gives the post-fetch timings this design's job arithmetic uses (§2.7). The readers had only the 29 October night, which built nothing.
