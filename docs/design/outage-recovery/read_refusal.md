# The refusal machinery, mapped for a night that recovers by itself

Read-only. Code read at `dev-ioxv9i` = 4590795 (one commit past 0702100; that commit touches page text only, `src/pages/lang/es.json`), plus `origin/feat/night-clock` at 84a81ee. Evidence from the night: the bucket's `state/refused.json`, `state/last-night.json` and `logs/2026-10-29/nightly-2026-10-29.log`. Nothing ran against the General Court, the SQL host or the bucket. The only thing executed was the assistant guard's `decide()`, offline, over six command strings.

"Guess" marks anything the code, the logs or the history do not show.

---

## 0. What happened on 29 October, as the code saw it

| When (UTC) | What | Where it is shown |
|---|---|---|
| 08:21:13 | Run 40841071509 starts on GitHub's machine. `state-down` brings nothing new (the bucket held no refusal) | log line 2–5; verdict `started`, `steps.state-down: success` |
| 08:21–08:27 | preflight, 356 s, exit 0 | log ~line 1653 |
| ~08:27:09 | `snapshot_gencourt` opens `https://gc.nh.gov/dynamicdatadump/`: **dropped**, `RemoteDisconnected`. That is drop no. 1 (`snapshot_gencourt.py:587-588`). A page *timeout* would have counted as "slow", not as a drop (`:257-262`) | log 1657 |
| ~4 s later (`--delay` 4.0, jittered, `:500`, `:592`) | `Docket.txt`: **dropped**. That is drop no. 2, so `refusal.note("snapshot_gencourt", why)` runs and the snapshot stops (`:618-623`). Because the page's drop already counted, the "once more in a minute" retry (`:624-630`) never ran | log 1658 |
| 08:27:15 | `archive/refused.json` is written with `epoch` 1793262435.0 (= 08:27:15 UTC). Its `at` is the runner's Eastern wall clock, `2026-10-29T04:27:14`. Snapshot exit 2, "(6s, exit 2)" | `r2/state/refused.json`; log 1660-1666 |
| after | The study views, the term data, the bill requests, the statutes and the lists are all skipped (`nightly.py:1587-1588`, `1626`, `1636`, `1641`, `1645`, `1653`: each is `not refusal.MARK.exists()`). The database fallback is never reached, because the export is "refused", not "empty" (`nightly.py:1587-1589`). Nothing is installed or built, so nothing is published | log 1668-1682; verdict `fetch: refused`, `files_from: none`, `built: false` |
| after nightly.py exits | Workflow step "A refusal goes to R2 at once" (`nightly.yml:449-459`) runs `cloud.py state-up`, which puts `state/refused.json` in the bucket | verdict `alerts[0]` |
| every later night | `state-down` brings it back (`nightly.yml:331-340`). `nightly.gc_quiet()` then fails at any age (`nightly.py:1233-1246`), so the night logs `FETCH DEFERRED: a refusal is on file`, exits 1 and alerts. **Nothing on GitHub can ever remove `state/refused.json`** (§3) | code path; `preflight._nightly_runner` 82537-82547 holds it |

The two requests were about four seconds apart. Both connections were accepted and then closed before any answer, which `refusal.classify` calls "dropped" (`refusal.py:295-299`).

---

## 1. `refusal.py`, the whole file (872 lines, `# GRANITE_VERSION: 2026-09-09.19`)

### 1.1 The record and its writers
- **`MARK = archive/refused.json`, `QUIET_HOURS = 24`** (`:105-106`).
- **`note(where, why)`** (`:113-127`) writes `{at, epoch, where, why[:300]}`. **The record carries no kind**: a 403, a block page and two drops all produce the same shape, and nothing says which machine met it or whether it was a dry run. On a stood-down laptop only (`_governing()`, `:545-565`, which is never true on GitHub, `:556-557`), it also calls `tell_the_bucket()`.
- **`tell_the_bucket()`** (`:135-185`) writes `archive/cloud/refusal-unsent.json` before it sends. It then calls `cloud.send_refusal`, and the marker is removed only once the bucket holds *this* refusal. It never raises.

### 1.2 The readers, and the three rules they apply
`force()` (`:195-208`) says it in its own words: three readers, three rules.
1. **`standing()` / `check()`** (`:211-252`). This is the rule for every hand-started fetch. A record younger than `QUIET_HOURS` makes the fetch exit **2**. An older one is ignored: `standing()` returns None when `hours > QUIET_HOURS` (`:219-220`). **So hand fetches already resume on their own after 24 h, and have done so since the first commit.** With no record standing, on a stood-down laptop, `check()` also exits **4** through `gc_turn()`.
2. **The lane** (`watchers/gc_lane.py:402-406`) stops at **any** `archive/refused.json`, whatever its age.
3. **GitHub's night** (`nightly.gc_quiet`, `nightly.py:1233-1246`) stops at **any** record. Its message is "clearing one is a person's decision, after netcheck.py".

`hours_left(d)` (`:188-192`) is the same age test as `standing()`, applied to a record held in memory. `cloud.py` uses it.

### 1.3 `classify(err=None, body=None)`, one reading for every fetcher (`:269-307`)
- **refused**: HTTP **403, 429 or 503**, **any `Retry-After` header** (whatever the status), or a body matching `BLOCKED = "Web Page Blocked|Attack ID"` (`:265`), the firewall's page, which is often served as a 200.
- **dropped**: `RemoteDisconnected`, `ConnectionResetError`, `ConnectionAbortedError`, **`ConnectionRefusedError`**, `TimeoutError`, `socket.timeout`, `ssl.SSLEOFError`, or a URLError whose reason says "timed out".
- **missing**: 404 or 410. **failed**: anything else.
- `BROKEN = "Runtime Error|Server Error in|Service Unavailable"` (`:266`) is **not used by `classify`**. Only `fetch_archive_docket.py:276` reads it, as an error page, not a refusal; `fetch_legislation.py:227` keeps its own copy. So a 200 page reading "Service Unavailable" counts as an error, while an HTTP 503 status counts as a refusal.
- The docstring says "One ends a run" for refused and "Two end a run" for dropped. The counting is done by each fetcher (§5); `classify` only names the kind.
- The comment at `:255-263` explains why 503 and Retry-After were made refusals: "a server shedding load says 503 with a Retry-After, which is a request to go away, not a flaky link".

### 1.4 One worker: `hold` (`:320-436`)
`archive/.lock` holds a pid and is touched every 60 s. A child of the lock's holder (the lane, or nightly.py) runs under the parent's lock (`:351-352`); anyone else exits **3**. `still()` (`:374-412`) is asked before each request: it is False inside GitHub's window on a stood-down laptop, and False under a lane whose lock is older than 180 s. `__exit__` turns a run the window cut short into exit 4 (`:426-436`).

### 1.5 The stand-down (`:456-493`)
`archive/runs-in-the-cloud.json` stops the laptop's nightly, its daily snapshot, `publish.bat` and the fetchers GitHub owns (exit **4**). It never applies when `GITHUB_ACTIONS == "true"` (`:473`). `--stand-down` writes the file (`:800-812`); deleting it is a person's act.

### 1.6 The night windows (`:496-544`)
`NIGHT_WINDOWS` (`:520-526`): every day 08:00–13:30 UTC, and Monday 04:00–06:30 UTC. `START_MARGIN_MINUTES = 30` (`:533`), `SOON_MINUTES = 60` (`:542`), and `CLOCK_ENV = GRANITE_CLOCK_UTC` for tests (`:538`). All of it governs **only a stood-down laptop**: `gc_turn()` returns None elsewhere (`:712-713`). GitHub itself read no window until the night-clock branch (§4.4).

### 1.7 `gc_turn()` and `refusal_read()` (`:678-744`)
On a stood-down laptop no General Court request starts:
- inside a window ("window");
- in the 30 minutes before one ("soon");
- or until a `cloud.py pull` has read the **real** bucket since the last window closed ("pull", `:730-743`). A `--local-bucket` read never counts (`:678-692`).

`window_check()` (`:747-773`) applies the window alone to the SQL host: "neither the refusal record nor the pull governs it".

### 1.8 `main()` (`:792-868`)
- `--clear` deletes `archive/refused.json` and `refusal-unsent.json` (`:839-850`). On a stood-down laptop it tells the person to run `cloud.py clear-refusal` as well (`:855-858`).
- With no flag it prints what is on file. With a record older than 24 h it prints "older than 24h and no longer stops anything" (`:861-863`). That is true for hand fetches and **false for the lane and the night**: the same message also appears in `force()`, but `main()` prints only the short form.

### 1.9 What the docstring promises (`:20-38`)
The rule exists because a calendar drain met two 403s and a chained run asked the same address 54 s later: "a refusal is a fact about the ADDRESS, so it has to outlive the process". Then, at `:35-38`: "Clearing it is a person's decision, deliberately … Nothing clears it automatically, because 'wait a bit and try again' is the behaviour that earns a longer block." (CLAUDE.md says "twelve seconds later"; the docstring says fifty-four. The two documents disagree.)

---

## 2. `netcheck.py`, the whole file (209 lines, `2026-09-04.4`)

**It makes eight requests, in this order, with `time.sleep(3)` after each (the last included). Each has a 45 s timeout.** All of them ask for `PATH = /senate/about_senate/about.aspx` (`:69`):

| # | Label (`:124-144`) | Host | How | User-Agent |
|---|---|---|---|---|
| 1 | our User-Agent, https | gc.nh.gov | urllib, HTTPS | **ours** (`OURS`, `:59-60`) |
| 2 | full browser headers | gc.nh.gov | urllib, HTTPS | browser (`FULL`, `:63-67`) |
| 3 | https, HTTP/1.1, raw socket | gc.nh.gov | http.client, HTTPS 1.1 | browser |
| 4 | https, HTTP/1.0, raw socket | gc.nh.gov | http.client, HTTPS 1.0 | browser |
| 5 | plain http, the real page | gc.nh.gov | http.client, **plain HTTP** 1.1 | browser |
| 6 | the other hostname, https 1.1 | www.gencourt.state.nh.us | urllib, HTTPS | browser |
| 7 | the other hostname, https 1.0 | www.gencourt.state.nh.us | http.client, HTTPS 1.0 | browser |
| 8 | "gc.nh.gov root, https 1.0" | gc.nh.gov | http.client, HTTPS 1.0 | browser |

So it sends **six HTTPS requests and one plain-HTTP request to gc.nh.gov, and two HTTPS requests to the other hostname**. Seven of the eight present a browser's User-Agent. **Test 8 is mislabelled**: `raw_try` always asks for `PATH` (`:109`), never `/`, so test 8 repeats test 4.

**How it names what came back** (`:152-163`):
- any `HTTPError` → "HTTP {code} -- the server ANSWERED";
- `RemoteDisconnected` or `ConnectionResetError` → "refused (closed without answering)";
- `socket.timeout` → "timed out";
- anything else → the exception's text.

It does not use `refusal.classify`.

**Its verdict cannot tell a block from a recovery.** `ok = out.startswith("HTTP")` (`:162`) counts a 403, a 429, a 503 and the 200 block page all as "got through". Eight 403s would print "Everything got through. Whatever it was has passed. Re-run the fetch that failed." (`:196-198`). Only the bodies it prints (`:167-184`) show the truth, and only to a person reading them. **A machine cannot use netcheck's last line as "it is back".**

**It is outside every guard:**
- it never calls `refusal.check()`, by design (`preflight.py:77676-77677`, `77741`);
- so on a stood-down laptop it also ignores `NIGHT_WINDOWS` and `gc_turn()`, and run inside 08:00–13:30 UTC it would be a second machine asking beside the night;
- it takes no `archive/.lock`;
- the assistant guard allows it without asking (`decide()` returned `allow` for `python3 netcheck.py`).

**What the 29 October check proved.** On 29 October it was run once, from a cloud container. That proves gc.nh.gov answered *that* machine's network path some eight hours later. It proves nothing about GitHub's runner (guess: a GitHub-hosted runner's egress address differs from night to night, which would also mean "a fact about the address" is weaker on GitHub than on the laptop; nothing in the repository records the runner's address).

---

## 3. `src/ops/cloud.py` and the refusal (4,195 lines, `2026-09-25.26`)

`cloud_kit.json`'s state list maps `archive/refused.json` to `state/refused.json`. Its description reads: "nothing asks the General Court, from either machine, until a person clears it." The dry-run state list includes `refused.json` too, so **a dry run's refusal stops main's night**, and by the same route a dry run's *lift* would reach main (`cloud.py:1923`; `cloud_kit.json` `dry_run.state`).

| Command | What it does to the refusal | Lines |
|---|---|---|
| **state-down** | Brings each state file down. A key the bucket lacks is **left alone here** ("an absence is not an instruction to delete"). A file changed here since the last state-down is kept. Records each sha in `archive/cloud/state-down.json` | `1995-2046` |
| **state-up** | Sends what changed here. **"One absent here is never removed there: a refusal is cleared by a person, not by a machine that happens not to hold it"** (`1638-1640`). It does not resend a copy recorded as `cleared` (`1661-1664`) or one the bucket dropped after this machine took it down (`1667-1671`). When both sides changed, a refusal is not a failure: the bucket's stands and this machine's goes to `replaced/<day>/state-conflict/` (`1680-1690`). Then `unsent_after()` (`1963-1992`) | `1627-1700`, `1919-1946` |
| **pull** (laptop only) | Reads the refusal first and records when and from which kind of bucket (`3243-3259`). `pull_refusal` (`2754-2860`): "A refusal only ever **arrives or stays** here" (`2756`). The bucket's copy is created here when the laptop has none (`2778-2785`, `create_whole`); of two copies the newer stands and the older is set aside. **A refusal the laptop holds and the bucket lacks is a FAILURE while it is under 24 h** (`2801-2807`), unless its sha is the one this machine recorded as `cleared`. It never removes the laptop's copy | `2746-2860` |
| **send_refusal / send-refusal** | Sends the laptop's refusal to `state/refused.json` **only when the bucket holds none** and never overwrites another (`2196-2207`); it waits behind that one with the unsent marker. It is not sent if its sha is this machine's recorded `cleared` (`2168-2174`). It goes to the real bucket only from the repository that holds `secrets.json` (`2175-2181`) | `2137-2226` |
| **clear-refusal** | Moves `state/refused.json` to `replaced/<day>/` (**never deletes**, `2103-2107`). Writes `files.refused.json = None` and **`cleared.refused.json = sha`** into **this machine's** `archive/cloud/state-down.json` (`2108-2112`). Exits 1 when a newer laptop refusal waited behind the cleared one (`2114-2127`). Its docstring says: "Clearing it is a person's decision, after netcheck.py" (`2057`) | `2049-2127` |

**The trap for any auto-lift.** The "cleared" fact lives only in the state record of *the machine that cleared it* (`STATE_RECORD`, `:411`). If GitHub's machine lifted the bucket's refusal, its `state-down.json` would vanish with the runner. The laptop would then still hold its pulled copy, and its next `pull` would report "THIS LAPTOP'S REFUSAL … IS NOT IN THE BUCKET" as a failure (`2801-2807`) and name `send-refusal`. That command would put the refusal back and stop the night again. **The lift therefore has to be recorded in the bucket**, and both `pull_refusal` and `send_refusal` must read it there.

---

## 4. The night: who reads the record on GitHub

### 4.1 `nightly.yml`
- **state-down** runs first (`331-340`).
- **"A refusal goes to R2 at once"**, `if: always() && statedown success && hashFiles('archive/refused.json') != ''` (`447-459`). It runs after nightly.py exits.
- **Final state-up** runs `always()` (`534-542`).
- The **Healthchecks** step sends `/fail` with `logs/alert.txt` as its body (`585-596`).
- **Concurrency**: a main run's group is its own `run_id` (`143-145`), so the workflow does *not* serialise a main night against a dry run started by hand. The one-night guarantee comes from the timer and the `started` job (`199-232`; `workers/night-timer/README.md`).
- The weekly has the same two refusal steps (`weekly.yml:134-175`).

### 4.2 `nightly.py` readers (dev)
- **Docstring at `26-30`**: "a refusal on file, at any age, means no fetch tonight (a run nobody watches does not decide a refusal is over)". Present since the first commit, 4bbe30d.
- **`gc_quiet()`** (`1233-1246`), the gate at `1541-1557`. When it fails, **the whole block is skipped: the web server *and* the SQL host's study views, term data and statutes**, all inside it (`1573-1654`).
- **In the loop**: `1587-1589` stops trying when `refusal.MARK.exists()`, *and* falls through to the database only when the export came back **"empty"**. A refused or dropped export never reaches `from_database`.
- **`from_database`** (`3011-3015`): "not asked: a refusal from the web server is on file, and carrying on by another door is a person's decision". Added in e55795f on 2026-10-01.
- **`take_documents`** (`3939-3943`) and the weekly (`5981-5985`). In the weekly, gc_quiet also holds its SQL steps, `5988-6003`, behind a web refusal, and fetch_committees has its own gate at `6005-6013`.
- **Sentences that name a person**: `1705-1706` "every fetch now waits for a person"; the verdict at `2283-2285`; `alerts_of` at `5758-5763` ("Every fetch waits until a person clears it: python3 netcheck.py …, then python3 src/ops/cloud.py clear-refusal"); `6013`.

### 4.3 The SQL host's own hold, an approved precedent for exactly this behaviour
`probe_db.py:73-110`, `HOLD_HOURS = (20, 44, 92, 164)` (`:115`), `note_connect_fail` / `note_connected` (`:193-230`):
- the hold **expires by itself and lengthens**, "each four hours short so that the night after finds it over";
- once it has expired, **one connection a night** is tried, and one that opens ends the hold;
- it is recorded **on GitHub's machine only** (`:196`) and travels in `state/`.

Its own words name the contrast: **"That is the deliberate difference from the web server's rule, where only a person clears a refusal: a month unattended needs it, and one connection a night is not what that rule exists to prevent."** (e55795f, 1 October; the commit says the person approved the database fallback.)

There is a contradiction here. `probe_db.py:109-110` says "A refusal from the web server does not hold this host, and the reverse", but `nightly.py:1541` and `5981` do hold the night's and the weekly's SQL steps behind a web refusal.

### 4.4 `origin/feat/night-clock` (84a81ee) and what it adds
- **`asking_left(minutes)`** (`nc nightly.py:3923-3955`) lets a step start only inside the daily window and only if it ends **before** `ASK_UNTIL = (12, 0)` UTC (`:721`).
- **`run(..., timeout=)`** kills a child at its limit, giving `RUN_KILLED = 124` (`:1192`, `:1239`).
- **`clock_kind()`** (`:3965`): "not asked for" never holds the gate.
- It gates only `take_lsrs` and `take_documents` (`:3987`, `:4080`). **The day's files keep their own rule**: a late night still asks the export whenever it runs.
- A refusal the night meets **"reaches the bucket only once nightly.py exits"** (`:716`). That is why 12:00–13:30 is left to the build.
- Its check `_night_clock` asserts that `asking_left`'s callers are exactly `["take_documents", "take_lsrs"]` and that the docstring says "those two steps ask between then and 12:00 UTC" (nc `preflight.py` ~92114-92207).
- A killed step does **not** note a refusal. It is "not taken" and stops the chain (EXITS).

---

## 5. Every fetcher's stop-loss

On a refusal or a second drop, each of these calls `refusal.note(...)` and exits **2**, unless the table says otherwise. preflight drives the bold ones through `main()` on fake answers (`preflight.py:77928-77975`; `{"403":1, "block":1, "drop":2}` means one 403 ends it, one block page ends it, and two drops end it).

| Script | 403/429/503/block | Drops | Notes |
|---|---|---|---|
| `snapshot_gencourt` (**the night**) | 1 (page or file) | **2, the page counting**; a file's first drop retried once after 60 s; a page *timeout* is "slow", not counted | `:584-588`, `:611-634`; checks `MARK.exists()` before the page and before every file, at any age (`:571`, `:595`); exit message "holds every fetch **for a day**" (`:683`) is wrong for the night |
| `fetch_lsrs` (**the night**) | 1, noted | **1 drop: exits 1 with *no* note** (`:117-120`, `:158-161`) | why `take_documents` is not asked after it (`nightly.py:3900-3935`) |
| `fetch_calendar_archive --listing` (**the night**) | 1, noted (`:609-611`, `:617-619`) | **1 drop: Stop(1), no note**, "the list waits for tomorrow" (`:612-616`) | the drain mode: 2 drops noted (`:1101-1112`), 2 failures in a row stop, 120 s cool-off |
| `fetch_committees` (**the weekly**) | 1 | 2 | `:220-241` |
| `fetch_archive_docket` | 1 (`stop_refused` counts a 403 as the whole budget) | `--stop-refused` default 2, 120 s cool-off | `:119`, `:251-267` |
| `fetch_legislation` | 1 | `--stop-refused` 2, 120 s cool-off | `:819-820`, `:956-973` |
| `fetch_senate_calendars` | 1 | `--stop-refused` 2 | `:160`, `:238-247` |
| `fetch_sponsors_by_member` | 1 | `--stop-refused` 2 | `:571`, `:655-665` |
| `fetch_journals` | 1 | 2 | `:136-141`, `:250-253` |
| `fetch_rollcall_parties` | 1 (503 too) | 2 | `:168-180`, `:460` |
| **`fetch_bill_status`, `fetch_bill_text`, `fetch_committee_details`, `fetch_members`, `fetch_session`, `resolve_members`, `probe_archive_shape`, `probe_schema`, `check_civics_links`** | 1 | 2 | driven |
| **`fetch_archive_bills`, `fetch_committee_reports`, `fetch_schedule`, `probe_calendars`** | 1 | stop at the first failure without noting one drop ("nor may one that stops at its first failure record a single dropped connection", `preflight.py:77840-77841`) | driven |

**On GitHub's night, only `snapshot_gencourt` can turn drops into a refusal record. In the weekly, only `fetch_committees` can.** The night's other web steps end on one drop without noting it.

---

## 6. The preflight checks that guard this, and what each asserts

Columns: **(a)** a record with an explicit resumable kind (absent kind = a person's), lifted only by the night; **(b)** an age-based expiry applied to every record; **(c)** the database used as the night's source while a web refusal stands.

| Check (dev `preflight.py`) | Asserts | (a) | (b) | (c) |
|---|---|---|---|---|
| `_nightly_guards` 81639-81690 | `gc_quiet()` False with a record `{"epoch":0,"where":"old"}`: **"a refusal from long ago let the nightly fetch"** (81660-81661) | holds (no kind) | **FAILS** | – |
| `_nightly_runner` 82270+ | record `{"epoch":0,"where":"snapshot_gencourt"}`, which is **this incident's writer**: night exits 1, logs `FETCH DEFERRED: a refusal is on file`, snapshot not called (82537-82547) | holds only if keyed on an explicit field, **not on `where`** | **FAILS** | – |
| `_nightly_falls_back` 89422+ | refusal on file means neither export nor database asked (90016-90018); refused export means no database (90019-90024, 90027-90033); refusal met in an empty pass means **"went on by another door"** fails (90112-90119) | holds | – | **FAILS by design: needs the owner** |
| `_cloud_state_and_site` 55274-55418 | clear-refusal **moves to replaced/, never deletes** (55341-55344); a cleared refusal is **never sent back** by state-up (55346-55348) | an auto-lift must keep both | – | – |
| `_cloud_pull` 58724+ | refusals cross both ways; the older is set aside, never dropped; a laptop refusal the bucket lacks **fails pull** while in force; clear-refusal exits 1 when one waited | trips unless pull learns a bucket-side "lifted" record (§3) | – | – |
| `_lane_daily` 78822+ | a refusal written as `'{}'` by a daily step stops the lane | holds if the lane is unchanged | **FAILS** if the lane expires | – |
| `_night_window` 92207-92481 | a standing refusal exits 2 before any window logic (92448-92450); the window only on a stood-down laptop, never on GitHub | holds | holds for a fresh record | – |
| `_every_fetcher_checks_refusal` 77646-77791 | every script holding a literal `gc.nh.gov` URL that makes a request calls `refusal.check()` (AST); **netcheck exempt by name** (77741); CONTRIBUTING's count held to it | a **new knock script** must call `check()` (which exits 2 at the very record it is testing) or be named exempt like netcheck; or the knock lives inside snapshot/nightly | – | – |
| `_every_fetcher_notes_refusal` 77799-78136 | each driven fetcher stops with 2 and a record after 1×403, 1×block page, 2 drops; **`fetch_lsrs` and `fetch_rollcall_parties` on a 503** (77970-77974) | holds if `classify` is unchanged and only *who lifts* changes | – | – |
| `_snapshot_stops` 81513-81636 | one 403 stops; a refused page stops before the files; a page timeout is "slow"; `--delay` ≥ 3 s | holds | – | – |
| `_offline_modes_ask_nobody` 78139 | fetching modes stopped by a fresh refusal (exit 2) | holds | – | – |
| `_refusal_reached_the_bucket` 94515 (data) | the unsent marker fails | holds | – | – |
| `_nightly_logs` 94549 (data) | seven nights meant to fetch that installed nothing fail; "waited out a refusal on file" is one reason (`NIGHTLY_WHY` 81707-81715) | – | – | – |
| `_alarm_stays_able_to_ring` 109835 | a refusal reaches the night's alert whatever warns | the alert sentence changes | – | – |
| `_stand_down` 91615 | the laptop runs none of the night; GitHub is never stood down | holds | – | – |
| `_assistant_guard` 67179+ | table of guarded calls: `refusal.py --clear` → ask (67211) | a new lift command needs a row | – | – |
| `_night_clock` (night-clock, nc ~92114) | `asking_left` gates exactly `take_documents` and `take_lsrs` | **changes** if a knock is gated by `asking_left` (it should be) | – | – |

---

## 7. Why it is built this way: the history

The repository's history starts on **2026-09-17** (4bbe30d). `refusal.py` is stamped as created on 2026-09-09 and `netcheck.py` on 2026-09-04, so their origins predate the history. "wait a bit and try again" and "a run nobody watches does not decide a refusal is over" are both already present in 4bbe30d.

| Commit | Date | What it set |
|---|---|---|
| 4bbe30d | 09-17 | `refusal.py`, `QUIET_HOURS = 24`, the docstring's "Nothing clears it automatically"; `nightly.py`'s "at any age" |
| cd3e77e | 09-18 | "Ten fetchers could walk through a standing refusal": every gc.nh.gov script calls `check()` |
| 749bab5, cdc00aa, 3d7752a | 09-25 | the night on GitHub; the stand-down; `state/refused.json` in R2 |
| 18055b1, d29c0f1, 1c9d712 | 09-26 | refusals cross both machines; `NIGHT_WINDOWS`; a laptop refusal waits behind the bucket's; only a real-bucket read frees the laptop; clear-refusal exits 1 when one waited |
| e55795f | 10-01 | the database fallback, **"carrying on by another door is a person's decision"**, and the SQL host's **self-expiring hold, "the deliberate difference"** |
| b279c7b | 10-07 | every `check()` caller also `note()`s; preflight drives fifteen of them |
| feat/night-clock | 10-26/27 | `asking_left`, `run(timeout=)`; the late night still publishes |

`git log -S'refused.json'` returns 45 commits, most of them incidental. The list above is the set that shaped the rule.

---

## 8. Documents that say "a person clears it" and would change

- `refusal.py:35-38`, `:195-208`, `:861-867`.
- `nightly.py:26-30`, `92-95`, `1241-1242`, `1705-1706`, `2283-2285`, `3012-3013`, `5761-5763`, `6013`.
- `watchers/gc_lane.py:29-37`, `403-405`.
- `cloud.py:230-242`, `2057`.
- `snapshot_gencourt.py:683` (it already says "for a day", which is wrong for the night).
- `cloud_kit.json`, the refused.json `what`.
- `CLAUDE.md:74-79`. This one is **already inaccurate**: it says the lane is held "for 24 hours", but the lane holds at any age.
- `CONTRIBUTING.md:24-31`, `README.md:344-353`, `SECURITY.md:93-98`.
- `ARCHITECTURE.md:113-117`, and `266-272`: "a refusal held for three nights is one email and its recovery is the sign it was cleared". That sentence would become "the sign it passed or was cleared".
- `watchers/README.md:71-83`.
- The night-clock branch's `THE NIGHT'S CLOCK` paragraph, if a knock is gated by it.

**The assistant guard has a gap today.** `.claude/hooks/guard.py:302-306` asks before `refusal.py --clear` and `cloud.py push|seed-kit|state-up`. **`cloud.py clear-refusal` and `send-refusal` are allowed without asking**, and so is `netcheck.py` (checked offline with `decide()`). `clear-refusal` is the command that actually frees the night.

---

## 9. THE MAP: where a self-recovery rule would have to be written

Every site below is required. Each one closes a gap the code shows.

1. **The record learns what it is: `refusal.note()`** (`refusal.py:113-127`).
   - Add `kind`, taken from `classify`'s word ("dropped" or "refused"; possibly "unavailable" for 503).
   - Add `machine` (github or laptop), `run_id`, `dry` (whether it came from a dry run), and a `lifts` ladder (count, last knock).
   - **A record with no `kind` stays a person's.** That keeps every existing caller, and every fake record in preflight (81660, 82539, 89555, 89589, `'{}'` in the lane check), working unchanged.
   - Callers that pass "dropped" on GitHub: `snapshot_gencourt.py:621` (and `:585` when the *page* is the second drop) and `fetch_committees.py:234-235`.
   - The laptop's own refusals stay a person's. That is the address blocked twice, and `probe_db`'s hold is likewise "recorded on GitHub's machine only".

2. **One rule in `refusal.py`, next to `standing()`, for example `may_knock(d, now)`.**
   - True only for kind dropped, `machine == github`, not dry, and age ≥ a wait.
   - **The wait must be under 24 h.** This incident's record is at 08:27:15. The next night's snapshot would ask at about 08:23–08:27 (08:17 start plus 6 min of preflight), **23.9–24.0 h later**. A 24 h rule would let the very next night through only by seconds, and not at all if preflight ran quicker. `probe_db`'s first rung, 20 h "so that the night after finds it over", is the tested precedent.
   - The ladder lengthens on each failed knock: (20, 44, 92, 164) h in `HOLD_HOURS`' shape.
   - After N knocks, or on any refused/block/403/429 answer, the record becomes a person's for good.

3. **The knock itself.** It runs once a night at most, from `nightly.py` on GitHub, before `snapshot_gencourt`:
   - under `refusal.hold("nightly")`;
   - gated by `asking_left()` (the night-clock branch), which changes `_night_clock`'s list;
   - one GET of a light page with **our own User-Agent**, read by `classify`.
   - **Not `dynamicdatadump/`**: opening that page "rebuilds every table before it answers" (`snapshot_gencourt.py:231-232`, `:570`).
   - **Not netcheck**: eight requests, browser User-Agents, a verdict that counts a 403 as passing, and no lock (§2).
   - Not a new script with a literal URL, because `_every_fetcher_checks_refusal` would require `check()`, and `check()` would exit 2 at the record. If a script is wanted, it needs a named exemption like netcheck's (77741).
   - A clean 200 that is not the block page lifts the record. Anything else re-notes it on the next rung and stops.
   - Whether the knock runs the **next night** or **later the same morning** is the owner's call. A same-morning knock from the job that met the drop is the "wait a bit and try again" the docstring forbids, and is one more request on a day already marked bad. A next-night knock costs one more stale day. The night already sleeps 30 min in-job between empty tries (`nightly.py:1617-1620`), so a same-job wait has precedent. Either way it must finish before 12:00 UTC (`ASK_UNTIL`), because a refusal reaches the bucket only when nightly.py exits (`nc nightly.py:716`).

4. **The lift, never a delete.** Move `archive/refused.json` aside, for example to `archive/refused-lifted/<epoch>.json`. This keeps `_cloud_state_and_site`'s "moved, never deleted" rule, and the record keeps its evidence.

5. **The bucket learns the lift: `cloud.py`.**
   - `state_up` can never remove `state/refused.json` (`1638-1640`), and `clear-refusal`'s "cleared" is local to the machine that ran it (`2108-2112`).
   - So add a bucket-side record (for example `state/refusal-lifted.json`, holding the lifted record's sha), written by the night only when the lifted sha equals the bucket's copy. The bucket's copy then moves to `replaced/`, as clear-refusal does.
   - `state_up` (`1627-1700`), `send_refusal` (`2168-2174`), `pull_refusal` (`2754-2860`) and `unsent_after` (`1963-1992`) must all read it. Otherwise the laptop's `pull` fails, `send-refusal` re-blocks, and `_cloud_pull`'s cases need new rows.
   - **Dry runs must never lift.** `cloud_kit.json`'s `dry_run.state` sends `refused.json` (`cloud.py:1923`); add the lifted record to `DRY_NEVER`, or never write it when `DRY_RUN` is set.

6. **The night's gate: `nightly.gc_quiet()`** (`nightly.py:1233-1246`, gate at `1541-1557`). Wrong order here would ask before a lift is decided, so the gate must run in this order:
   1. a person's record defers, as today;
   2. a resumable record that is not yet due defers, with a sentence that says when the knock comes;
   3. a due record knocks, which leads to the lift, then the night as usual.

   The weekly's `gc_quiet` (`5981`) follows the same rule or stays a person's (decision). `snapshot_gencourt.py:517`, `:571`, `:595` and `refusal.check()` need no change, *provided the lift has already moved the file* before snapshot runs.

7. **The laptop.**
   - The lane (`gc_lane.py:402-406`) can stay as it is: it stops at any `archive/refused.json`, and the laptop is attended.
   - But `pull` must then either set aside the laptop's copy when the bucket says "lifted", or report it as a line rather than a failure. That is a decision for the owner, and it touches `_cloud_pull` and `_lane_daily`.
   - `gc_turn()`'s "pull" rule (`refusal.py:730-743`) already makes the laptop read the bucket after every window, so it learns of a lift the same way it learns of a refusal.

8. **The alert and the words.**
   - `alerts_of` (`nightly.py:5758-5763`) says "until a person clears it". For a resumable record it should say when the next knock is due, and that a person may still clear it.
   - The verdict sentence at `2283-2285`, the docs (§8), and the guard row for any new command (`_assistant_guard`).

9. **The checks to write.** A resumable record at 20 h knocks once, and a 200 lifts it. A block page or 403 on the knock makes it a person's. A fresh record never knocks. A laptop record, a dry-run record or a record with no kind never knocks. Two knocks never happen in one night. The bucket record survives `pull` and `send-refusal`. A dry run never lifts.

### Guarantees the rule must keep (where each lives)
- **One fetch at a time across both machines.**
  - `archive/.lock` and `hold.still()` (`refusal.py:320-436`).
  - The laptop's window and margin (`:520-533`, `gc_turn` `:707-744`, `window_check` `:747-773`).
  - One night a day (`nightly.yml:199-232`; night-timer).
  - The knock runs *inside* the night's own job and lock. A second dispatch would be stood down by `started` anyway.
  - Caveat from code: the workflow's concurrency key (`nightly.yml:143-145`) does not stop a dry run by hand from overlapping a main night.
- **A refusal outlives the run that met it.**
  - `note()` writes first; `state-up` runs on `always()` (`nightly.yml:449-459`, `534-542`); the laptop sends at once (`refusal.py:126-127`).
  - The lift must be decided by a *later* knock, never by the run's own next request. Records are moved, not deleted.
- **The lane.** It stops at any record and on any non-zero step (`gc_lane.py:29-37`, `402-406`, `462-467`), and learns of the night's refusals only through pull.
- **The stand-down.** The laptop never runs the night; GitHub is never stood down (`refusal.py:467-493`; `_stand_down`).
- **A true block stays a person's.** 403, 429, the block page, and (decision below) 503 or Retry-After. One such answer to a knock also turns a resumable record into a person's.

---

## 10. Where the owner's idea helps, and where it cannot

- **It cannot prove the web server is back.** The live Worker reads PublicSQL over TDS and "never gc.nh.gov" (`design_final.md` §0, §6.1), and preflight's network boundaries keep code that way. On **29 October it would not have read the SQL host at all**: its states are hot, warm, a heartbeat on weekdays "from 1 January to 30 June", and off otherwise (§2.3). Only its YouTube half would have run.
- **It writes its own bucket, `graniterecord-live`** ("one writer each", §4.4). The night holds credentials only for the kit's bucket (`R2_BUCKET`, `nightly.yml:334-337`), so the night reading the Worker's health would be a new secret and a new coupling.
- **It does help in four ways:**
  - **(i)** From January to June a healthy heartbeat says the General Court's *database* answers Cloudflare. That is evidence for the outage-versus-block question that netcheck from a third machine is not, though still not about the web server.
  - **(ii)** The SQL host is the IT office's sanctioned door ("No problem hitting PublicSQL during a session as it doesn't touch the website"). **Using the database as the night's source while the web server is out** needs three changes: `from_database`'s person rule (`nightly.py:3011-3015`); the loop's "only after an empty export" (`1587-1589`); and `gc_quiet`'s coverage of the SQL steps (`1541`; weekly `5981`), which already contradicts `probe_db.py:109-110`. With those changes the site would stay fresh during a web outage without one more request to gc.nh.gov. This touches `_nightly_falls_back` (90016, 90022, 90112) and needs the owner's OK.
  - **(iii)** Live Now and live votes keep the visible part of the site current while the night is held.
  - **(iv)** The Worker's own hold table (§2.6: three failures in a row lead to a 30-minute hold, then one try, then the rest of the day) is the same expiring-hold idea, already designed.

---

## 11. On 503, for the decision

- In this code, the firewall's block has always been a page served as a **200** carrying "Web Page Blocked / Attack ID" (`refusal.py:265`, the preflight fixtures).
- Their export's own failure was also a 200 page ("Error Generating … Execution Timeout Expired", `snapshot_gencourt.py:236-246`).
- Nothing in the repository records an HTTP 503 from gc.nh.gov.
- `classify` treats any 503, and any Retry-After, as a request to go away (`refusal.py:261-263`, `286`), and preflight holds `fetch_lsrs` and `fetch_rollcall_parties` to that (77970-77974).

**Recommendation (a judgement, not shown by the code):**
- keep `classify` as it is, so the run still stops at once;
- record a 503 **with** `Retry-After` as resumable, but never knocked before both the Retry-After time and the next rung;
- record a bare 503 as resumable on the longer ladder;
- 429 stays a person's: it is a rate complaint aimed at us.

---

## 12. Stated as guesses
- A GitHub-hosted runner's egress address differs from night to night. If so, a refusal on GitHub is less "a fact about the address" than on the laptop. The repository does not record it.
- A cloud container's 200s at about 16:30 UTC say nothing about the runner's address at 08:27.
- The 20 h first rung and the (20, 44, 92, 164) ladder are borrowed from the SQL hold and have not been measured against gc.nh.gov.
