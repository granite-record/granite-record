# Fresh while the web server is out: the database as the night's source, and a hold that tests itself

Design only. Nothing was run against the General Court, its SQL host or YouTube. Nothing tracked was edited.
I read the bucket read-only: one listing of `kit/` and `state/`, with no download.

- Code read at `dev-ioxv9i` = `origin/dev` = `4590795`. That is one commit past `0702100`, and it touches only page text.
- `origin/feat/night-clock` is now at **`22d19e4`**, past the `84a81ee` in the brief. Its additions are a merge of dev and a stamps commit, plus `f48edfe`: a reading between 12:00 and 13:30 UTC now says "outside the hours".
- I checked the readers' facts at the lines cited. Where my own reading adds to theirs, I give the line.
- "Guess" marks anything the code, the logs or the history do not show.

---

## 0. The design on one page

**What went wrong, as the code shows it.**
- Two dropped connections, 4 seconds apart, became a refusal record with no kind (`refusal.py:113-127`).
- The night sends the day's files to the database only when the export was *empty* (`nightly.py:1587-1589`). `from_database()` refuses outright whenever any refusal is on file (`nightly.py:3011-3015`).
- Every later night stops at any record, of any age (`nightly.py:1233-1246`, `1541`). Nothing on GitHub can remove the bucket's copy (`cloud.py:1637-1640`).
- So a website hiccup stopped the one source the General Court's IT office said is fine to ask at any time. It stopped it for as long as nobody came.

**The design has three parts.** Each is small, and each uses what is already there.

1. **The record says what it was.**
   - `refusal.note()` gains `kind`, from the answer, plus the machine, the branch, whether the run was a dry run, and an `id`.
   - **dropped** means two dropped connections or timeouts. **unavailable** means an HTTP 503. Both are *resumable*.
   - **refused** means a 403, a 429, the firewall's block page, or any `Retry-After` on another status. It is a person's, and so is **any record with no kind**. That includes every record written before this change and the one standing now.

2. **A resumable record closes only the web server.**
   - The night takes the day's seven changing files from the General Court's database through the existing `from_database()`. Every guard it already has stays: `dayfiles_from_db.judge`, the shrink rule, `DB_LOOKED_WRONG`, `DB_STOPPED_MOST` and the SQL host's own hold.
   - It builds, and it publishes as any database night does. Under the person's decision of 6 October 2026, a database night "never holds" (`nightly.py:928-946`).
   - It does this **at once on the night the drops happen**, and on every night the hold stands.
   - It asks the web server nothing else: no export, no bill requests, no lists.

3. **The night alone tests the web server, and lifts the hold itself.**
   - The test is **one** request, called "the knock": `https://gc.nh.gov/downloads/Members.txt`, a file the night already asks every night (`snapshot_gencourt.py:122`).
     - It is 82,694 bytes in the kit today.
     - It is not the `dynamicdatadump/` page, which makes the General Court rebuild every table (`snapshot_gencourt.py:217-232`).
     - It carries our own User-Agent.
   - When the knock is made:
     - from GitHub's runner on `main`, never on a dry run;
     - under the night's own lock;
     - inside 08:00–12:00 UTC (the night-clock's `asking_left`);
     - never by the run that met the refusal;
     - only once the record's rung has passed. The rungs are **16, 40, 88 and 160 hours**: the next morning, then 2, 4 and 7 days on.
   - What its answer does:
     - **A clean answer lifts the hold.** The record is moved aside, never deleted, and the lift is written to the bucket as `state/refusal-lifted.json`, so the laptop and `send-refusal` do not put the record back. The night then asks the export as usual.
     - **A refused answer** (403, 429 or the block page) makes the record a person's.
     - **A drop or a 503** moves the record up a rung.
     - **Four failed knocks** make it a person's as well. The database still keeps the site current.

**29 October replayed under this design.**
- The two drops at 08:27 UTC, then the database at once, then the build, then a publish without approval.
- On 30 October at about 08:23 UTC, one request for `Members.txt`. If it is answered, the hold lifts and the night is ordinary.
- The site is never a day stale. The General Court is asked one more request than today and seven fewer than a `netcheck.py` run.

**What stays a person's.**
- 403, 429 and the block page.
- A record with no kind, a laptop's record and a dry run's record, as far as the web server is concerned.
- A hold after four failed knocks.
- A database night the guards stop.
- The new term.
- The approval gate's reasons.

**What needs the owner's word** (§10):
- the database while the web server is held (this changes "carrying on by another door is a person's decision");
- the knock and the lift;
- 503 as resumable;
- where the first notice goes;
- the CLAUDE.md paragraph.

---

## 1. What the code does today, and the exact places it stops

| Step | What happens on a refusal | Where |
|---|---|---|
| The record | `{at, epoch, where, why}`. No kind, machine, branch or dry flag. A drop and a 403 look the same to every reader after it | `refusal.py:113-127` |
| The snapshot | The page's drop counts as the first of two (`:587-588`). The second drop notes the record and stops (`:618-623`), so the file's 60 s retry (`:624-630`) is never reached. Exit 2 | `snapshot_gencourt.py:578-630, 682-685` |
| The try loop | Breaks on anything but `empty`, or on any record on file, so a refused export never reaches the database | `nightly.py:1587-1589` |
| `from_database` | "not asked: a refusal from the web server is on file, and carrying on by another door is a person's decision" | `nightly.py:3011-3015` |
| After the loop | The study views, term data and statutes (all from the database), and the bill requests and lists (both web), each need `not refusal.MARK.exists()` | `nightly.py:1626, 1636, 1641, 1645, 1653` |
| Later nights | `gc_quiet()` is false on any record, at any age, so nothing is asked of either host | `nightly.py:1233-1246, 1541-1557` |
| The weekly | Defers everything on `gc_quiet()`, its four database-only pieces included | `nightly.py:5981-5985` |
| The bucket | `state_up` never removes `state/refused.json`. Only `clear-refusal`, run by a person, moves it, and it records "cleared" only on the machine that ran it | `cloud.py:1637-1640, 2049-2112` |
| The laptop | A laptop copy the bucket lacks makes `pull` FAIL while it is under 24 h, unless that machine cleared it | `cloud.py:2801-2807` |

**Where "another door" came from.** The phrase first appears in the code of `e55795f` (1 October 2026). Its commit message says "with no refusal and no hold on file" and quotes no person on it. `fetch_day_db.py:63-66` calls it "the person's rule about carrying on by another door". Whether the owner said those words is not shown. Either way, changing it is the owner's decision.

**Against it in the code itself:**
- `probe_db.py:109-110`: "A refusal from the web server does not hold this host, and the reverse."
- `probe_db.py:87-89` calls its own self-expiring hold "the deliberate difference from the web server's rule ... a month unattended needs it".

**Against it in the record.** PublicSQL answered whole on every database night: 3, 4, 5, 6 (rerun), 9, 11 (dry) and 12 October (`read_history.md` §2b). A web refusal has never been met on that host.

---

## 2. The rules, exactly

### 2.1 What a record is, and what each kind opens

`refusal.note(where, why, kind=None, retry_after=None)` writes these fields:
- `at`, `epoch`, `where` and `why`, as today;
- **`kind`**;
- **`machine`**: `"github"` when `GITHUB_ACTIONS == "true"`, else `"laptop"`;
- **`ref`**: `GITHUB_REF`;
- **`dry`**: `DRY_RUN == "true"`;
- **`run_id`**;
- **`id`**: `run_id` and `epoch`, carried unchanged through every rewrite;
- **`since`**: the first epoch of this outage;
- **`knocks`**: `[]`;
- **`rung`**: 0;
- **`retry_after_until`**, when a 503 named one.

| Kind | What sets it | The database door (`refusal.db_door`) | The web knock (`refusal.knock_due`) | Who lifts it |
|---|---|---|---|---|
| none (every old record, and every `note()` caller not changed below) | — | **closed** | never | a person (`refusal.py --clear`, `cloud.py clear-refusal`) |
| `refused` | 403, 429, the block page, a `Retry-After` on any status but 503 | **closed** (owner decision D2) | never | a person |
| `dropped` | the snapshot's second drop (`snapshot_gencourt.py:618-623`), the weekly's `fetch_committees` second drop (`fetch_committees.py:233-235`), a knock that drops or times out | **open** | when `machine == "github"`, `ref == "refs/heads/main"`, not `dry`, `rung < KNOCKS_MOST` and the rung's hours have passed | the night's knock, or a person |
| `unavailable` | HTTP 503, with or without `Retry-After` (§2.7) | **open** | as `dropped`, and never before `retry_after_until` | the night's knock, or a person |
| any kind, with `person: true` | a knock refused; four knocks failed | open for `dropped`/`unavailable`, closed for `refused` | never | a person |

Two things follow from this table:
- **The database door depends only on the kind.** It never asks the web server, so a mislabelled kind (dev code on a dry run, for example) can cost database queries the IT office has okayed, but never a web request.
- **The knock depends on the kind *and* on who wrote the record.**
  - A laptop record is about the laptop's address. GitHub's knock cannot prove anything about that address.
  - A dry run's record was written by code that is not on `main`.
  - Neither is ever knocked or lifted by the night.

`classify()` does not change (`refusal.py:269-307`). A 503 still stops a run at once. Only the *record* tells 503 apart, through a new `refusal.record_kind(err, body)`, which `snapshot_gencourt` passes to `note()`.

### 2.2 The night's order (`nightly.py` main, replacing `1541-1706`)

1. **`gc_quiet()`** keeps its signature (`(ok, why)`) and its meaning: *may the web server be asked tonight*. It is false on a held lock and on any record.
2. **`db_quiet()`** is new: *may the SQL host be asked tonight*. It is false on a held lock and on a record whose door is closed. It is true when there is no record, or a resumable one.
3. If both are false: "FETCH DEFERRED", exactly as today (`1554-1557`).
4. Otherwise take `refusal.hold("nightly")` (`1574`), then:
   1. **If `refusal.knock_due()`, `knock_web(night)` runs** (§2.4). It is gated by `asking_left(KNOCK_MINUTES)` and killed at `seconds_left(deadline)`.
      - **Lifted:** the web server is open; go to step 2.
      - **Not lifted:** the web server stays closed.
      - **Made a person's:** both doors are closed, and the night stops as in step 3, with the knock's line in `tried`.
   2. **If the web server is open:** run the try loop as today, with one change at `1587-1589`.
      - A try whose status is `refused` with a record on file whose door is open goes to `from_database()` **at once and once**, exactly as `empty` does today (`DB_AFTER_TRIES = 1`).
      - The export is not asked again that night: `last = tries`.
      - An `empty` export with no record on file is unchanged.
      - A `did not complete` (a page where a file should be, a single drop, any other failure) is unchanged: nothing more is asked, by any door (`2766-2775`).
   3. **If the web server is closed and the database is open:** no try of the export.
      - `night.v["fetch"] = "held: ..."`, and `tried` gets the hold's line.
      - `from_database(a, night, 0, asked, because=...)` is called once.
   4. **After the loop:**
      - The study views (`1626`), the term data (`1636`) and the statutes (`1645`) need `(rc == 0 or db_day) and db_door_open()`, not `not MARK.exists()`.
      - The bill requests (`1641`) and the lists (`1653`) need **no record on file**, as today. Otherwise they are `"not asked for: " + WEB_HELD_SAID`, and the copy on file is kept.

`from_database()`, at `3011-3015`:
- It refuses only when `not refusal.db_door()`. Its log line and its `tried` line say the record is one only a person may lift.
- Its `because` names the cause in the project's words (§3). Today it is hard-wired to "the export came back empty".
- Everything else in it is unchanged:
  - the SQL host's own hold (`probe_db.hold_standing`);
  - "no installed files";
  - `judge()`'s stops;
  - the shrink rule through `snapshot_gencourt.install()`;
  - `Members.txt` from tonight's snapshot, or the installed one kept (`3086-3108`). On a held night none arrived, so the installed one stays and the page says so.

**What the database night still respects** (the content guards, untouched):
- `dayfiles_from_db.judge()`'s stops (`dayfiles_from_db.py:2125-`): a bill missing, a docket behind, a row reworded beyond its ceiling, a term turning over. Any stop means nothing is installed. The night is not clean, its page says what stopped it, and `DB_STOPPED_MOST = 2` is an error (`nightly.py:1085-1097`, `5386-5394`).
- `DB_LOOKED_WRONG` ends the night's asking (`2614-2645`).
- The new term: the database is never the source of a turn. A New term run never asks it (`3006-3010`), and the guards stop a newer year.
- **One rule changes.** `TRIES_AFTER_DB` ("ask the export once more, `EMPTY_WAIT` minutes later", `2581-2593`) does not apply while the web server is held. A database that cannot be used under a hold ends the night with nothing installed. It is not clean, and the alert says why (§3).

### 2.3 When a web-server drop or refusal still lets the night take the database and publish

| Tonight | The database asked? | Published? |
|---|---|---|
| The export arrives whole | no (one source a night, as today) | as today |
| The export is empty, no record | yes, at once (today's rule) | yes, a database night |
| **Two drops, or a 503, met tonight on GitHub (any branch)** | **yes, at once, once, under the same lock** | **yes, a database night**, unless its guards stop it or a gate reason that is not the fallback's holds it (a release with no proving dry run, a failed "hold"-tier check) |
| **A resumable record on file, knock not due, not allowed by the clock, or a dry run** | **yes**, with no request to the web server | **yes**, as above |
| **A resumable record on file and a knock that drops or gets a 503** | **yes**, after the one knock | **yes** |
| A resumable record on file and a knock that answers | no: the hold lifts, the export is asked, and if it then drops twice the record is re-noted at the next rung (§2.5) and the database is asked at once | yes |
| A 403, a 429, the block page, or a kindless record (now, or met tonight, or met by the knock) | **no** | **no** (as today) |
| A laptop's or dry run's resumable record | yes | yes. The web server waits for a person, and the alert says so |
| A page served where a file should be, or a single drop with no refusal (`did not complete`) | no (as today, `2766-2775`) | no |
| A New term run | never the database (as today) | as today |

**Why the database is asked on the very night of the drops, and not only on the nights after.**
- The SQL host is a different server: `66.211.150.69`, `probe_db.py:67`, against the website at `gc.nh.gov`.
- The IT office said asking it "doesn't touch the website".
- `probe_db`'s hold already stops it on a failed connection, for 20 hours at the least (`probe_db.py:115`).
- Waiting a night would only make the site a day stale for nothing.
- *Guess:* if the General Court's perimeter dropped GitHub's address for both hosts, the first connection fails, `probe_db` records its own hold, and nothing more is asked. That is self-limiting.

**Why no second try of the web server later the same morning.** The database keeps the site current, so there is nothing to win by a same-day retry. A same-day retry from the job that just met the drops is the "wait a bit and try again" that `refusal.py:35-38` warns against. The knock waits a day.

### 2.4 The knock

**Where.**
- `snapshot_gencourt.py --knock`. Its literal URL (`EXTRA`, `:122`) and its `refusal.check()` are already there.
- So `_every_fetcher_checks_refusal` (`preflight.py:77647`) needs no exemption, which is netcheck's case at `:77741`.
- It is run by `nightly.knock_web()` as a child, under the night's `refusal.hold`.

**The gate.** `refusal.check("The knock", knock=True)`:
- passes only a record for which `knock_due()` is true;
- exits 2 for anything else, as today.

So the 24-hour rule for hand fetches (`refusal.py:211-252`) is unchanged, and the knock cannot be started by hand on the laptop: `machine == "github"` and `GITHUB_REF == refs/heads/main` are required, and `DRY_RUN` must not be `true`.

**Write first.** Before the request, the record is rewritten with `knocking: <epoch>`. A run that dies mid-knock has then still used its rung, and the always-run "A refusal goes to R2 at once" step (`nightly.yml:449-459`) carries that rewrite up. This is `tell_the_bucket`'s pattern: write the marker, then act (`refusal.py:135-150`).

**The request.**
- One GET of `https://gc.nh.gov/downloads/Members.txt`, with the snapshot's own `UA` (`:124-125`).
- A 60 s timeout (`KNOCK_TIMEOUT`), through `read_one()` (`:333-349`).
- A clean answer is `read_one`'s: a body of at least 40 bytes (`MIN_BYTES`) that is not HTML and not the block page.
- Nothing else is asked. The body is not installed, because the export asks it again if the hold lifts. That costs one duplicate 83 KB request on a lift night; reusing it is a later refinement.

**The clock.**
- `asking_left(KNOCK_MINUTES = 2)` and `run(timeout=seconds_left(deadline))` come from the night-clock branch.
- A night GitHub starts late, after 12:00 UTC, never knocks. It takes the database, and the next on-time night knocks.
- *This makes the design depend on `feat/night-clock` being merged first* (§5).

**What it does with the answer** (`refusal.knocked(answer, said)`, the one writer):

| Answer | Record | Exit | The night |
|---|---|---|---|
| clean | moved to `archive/refusals-lifted/<id>.json`; `archive/refusal-lifted.json` written: `{id, lifted_at, run_id, rung, since, knock: {url, bytes, seconds}, record: <the whole lifted record>}` | 0 | web open: the export as usual |
| `dropped` (incl. timeout, and `RUN_KILLED` 124, which nightly turns into this) | `knocks += [{at, answer}]`, `rung += 1`, `epoch` = now; `person: true` at `rung == KNOCKS_MOST` | 1 | web closed, database open |
| `unavailable` (503) | as dropped; `retry_after_until` = now + Retry-After, capped at 168 h | 1 | web closed, database open |
| `refused` (403, 429, block page) | `kind = "refused"`, `person: true` | 2 | both closed; not clean; alert |
| `missing` (404/410) or `failed` | as dropped (never a lift), with the answer named | 1 | web closed, database open |

**The ladder.** `KNOCK_HOURS = (16, 40, 88, 160)` and `KNOCKS_MOST = 4`.

| Rung | Due at | Why |
|---|---|---|
| 0 | `epoch + 16 h` | the next morning, wherever yesterday's refusal fell |
| 1 | `epoch + 40 h` | two days on |
| 2 | `epoch + 88 h` | four days on |
| 3 | `epoch + 160 h` | seven days on |

- **Why 16 h for the first rung, and not 24 h or more.** A refusal at 08:27 is 23.9 hours old by the next night's 08:23 knock. So 24 h would let the next night through only by seconds, or not at all (`read_refusal.md` §9.2). A refusal met by a GitHub-delayed night as late as 16:00 UTC is still 16.3 h old by 08:17 the next day.
- **Each later rung is a whole number of days less 8 hours,** in `probe_db`'s pattern of "each four hours short so that the night after finds it over" (`probe_db.py:84-85`).
- **The knock itself cannot repeat within a day.** It runs once per rung, only inside 08:00–12:00 UTC, and only from the night's job, which runs once a day (the timer and `started`, `nightly.yml:199-232`). So the 16 h is not what stops a same-day retry.
- **On 29 October's dates:** 30 Oct, 1 Nov, 5 Nov, 12 Nov.
- *These numbers are my reading, not measured against gc.nh.gov.* The recorded outages ended within 61 minutes, about 8½ hours, about 8 hours, and one night (`read_history.md` §3C).

**Why `Members.txt`.**
- The night asks it every night, so it is never an invented path. The first block was earned "probing filenames that did not exist" (`CLAUDE.md:56-57`).
- It is small: 82,694 bytes in the kit today.
- It lives under `/downloads/`, not `/dynamicdatadump/`. That page "rebuilds every table before it answers" (`snapshot_gencourt.py:231-232`), the heaviest request the night makes, and the wrong thing to ask of a server that may be in trouble.
- *Guess:* that `/downloads/` is served by the same front door as `/dynamicdatadump/`. If it is not, a knock can pass while the export still drops. §2.5's lift memory bounds that to at most 3 requests on such a night.

**Why not `netcheck.py`.**
- It makes 8 requests: 7 to gc.nh.gov, one of them over plain http, plus 2 to another hostname.
- 7 of the 8 carry a browser User-Agent.
- It counts a 403 or the block page as "got through" (`netcheck.py:162, 196-198`).
- It takes no lock and checks no window.
- It stays what a person runs.

### 2.5 The lift: local, bucket, laptop

**On the runner.**
- The record is moved aside, never deleted. This keeps `_cloud_state_and_site`'s "moved, never deleted" (`preflight.py:55341-55344`).
- `archive/refusal-lifted.json` carries the whole lifted record.

**To the bucket.**
- `refusal-lifted.json` becomes a state file: a new entry in `cloud_kit.json:196-219`, as `state/refusal-lifted.json`. It is added to `DRY_NEVER` (`cloud.py:457`) and never listed in `dry_run.state` (`cloud_kit.json:226`).
- `state_up()` (`cloud.py:1627`) first runs **`lift_in_bucket()`**, only when this is not a dry night (`only is None`) and `GITHUB_ACTIONS == "true"` and `GITHUB_REF == refs/heads/main`. It is a compare-and-move:
  - the bucket's `state/refused.json` must carry the lifted `id`;
  - its sha must equal the one this machine's `state-down` recorded (`archive/cloud/state-down.json` `files["refused.json"]`). That means the bucket has not changed since the night took it down.
  - If both hold, it is moved to `replaced/<day>/lifted/refused.json`, as `clear-refusal` does (`cloud.py:2103-2107`), and recorded as `cleared` in the state record, so that no `state_up` sends it back.
  - Otherwise nothing is moved, and the night's page says the bucket held another refusal.
- After the lift, a new record noted later the same night (a lift, then two drops) goes up as an ordinary new file. The bucket then holds none, and `state_up`'s `old is None` path sends it.
- The workflow step "A refusal goes to R2 at once" (`nightly.yml:447-459`) changes its `if` to `hashFiles('archive/refused.json', 'archive/refusal-lifted.json') != ''`, so a lift reaches the bucket before the build, as a refusal does.

**On the laptop.**
- `pull_refusal()` (`cloud.py:2754`) reads `state/refusal-lifted.json`. A laptop copy whose `id` it names is set aside, not deleted, as the older of two refusals already is (`cloud.py:2830-2838`). The line says "the night lifted this refusal after one request was answered". It is not the failure at `2801-2807`.
- `send_refusal()` (`cloud.py:2137`) never sends a record whose `id` the bucket's lift names. This mirrors `cleared` at `2168-2174`.
- `gc_turn()`'s rule that the laptop must pull after every window (`refusal.py:730-743`) is how the laptop learns of a lift, as it learns of a refusal.
- The lane is unchanged (`gc_lane.py:402-406`). It stops at any record, and once `pull` has set the lifted copy aside there is none.

**Lift memory.**
- A resumable record noted within `LIFT_MEMORY_DAYS = 14` of a lift starts at `rung = lifted.rung + 1` and keeps the lifted record's `since`.
- So a server that answers the knock and then drops the export does not get a fresh 16-hour ladder every day. *14 is my number.*

**Dry runs never lift.** There are three locks:
- `nightly.py` never calls `knock_web()` when `a.dry_run`, `dry_by_workflow()` or `not_main()` holds (`nightly.py:2067-2097`);
- `refusal.check(knock=True)` exits 2 when `DRY_RUN` is `true` or the ref is not exactly `refs/heads/main`;
- `state_up` never runs `lift_in_bucket` on a dry night, and `DRY_NEVER` stops `refusal-lifted.json` from being sent.

### 2.6 Escalation

| Failed knocks | Where the person hears it | Knocks left |
|---|---|---|
| 0 or 1 | the **warnings'** check (`warns_of`, `HEALTHCHECKS_WARN_URL`), recommended (D5) | 3 or 2 |
| 2 or 3 | the **night's** check (`alerts_of`), so an email when it goes down (`nightly.py:5680-5689`) | 2 or 1 |
| 4, or any refused answer | the night's check. The record is a person's. For `dropped`/`unavailable`, the database still keeps the site current | 0 |

- **Seven database nights in a row** stays the error on the run's page it is today (`DB_NIGHTS_MOST = 7`, `nightly.py:1084, 5381-5385`). Its sentence is generalised from "its export came back empty" to the cause on file.
- **Why escalate at all, when the site is current.**
  - The only first-hand description of a block in the repository is drops on everything (`netcheck.py:11-19`).
  - After a run of database nights, the guards compare the database's files with the database's own (`nightly.py:2607-2609`).
  - The web-only pieces age: `Members.txt`, the six lookups, the bill requests, the calendar and journal lists, and the weekly's committee rooms.
  - Two weeks of drops is a person's question.

### 2.7 503, decided

- **`classify` is unchanged.** A 503 is `refused` there, so a run stops at the first one. preflight's 503 tests for `fetch_lsrs` and `fetch_rollcall_parties` (`preflight.py:77970-77974`) stay green.
- **The record calls a 503 `unavailable`: resumable, with the database door open.**
  - The knock is never made before `max(rung hours, Retry-After)`, with the Retry-After capped at a week.
  - A 503 on the knock is a failed knock, never a lift.
- **Why:**
  - HTTP's own meaning of 503 is a temporary inability to serve, and `Retry-After` is the server saying when.
  - The rule honours that literally: nothing is asked before then, and only one request after.
  - No 503 from the General Court is recorded anywhere (`read_history.md` §3B).
  - The firewall's known shapes are a 403 and the 200 block page (`refusal.py:265`).
- **429 stays a person's.** "Too many requests" is aimed at our behaviour, and answering it with a timer is exactly the wrong reflex.
- **A `Retry-After` on anything but a 503** stays `refused`.
- **The risk:** *guess*, some firewalls answer a block with 503. If theirs does, the ladder ends at a person's in 14 days, with the night's check down from the second failed knock.

### 2.8 The weekly, the laptop, a New term run

- **The weekly (`nightly.py:5981`).**
  - A person's record defers everything, as today.
  - Under a resumable record, its four database pieces run (`5987-6003`). `fetch_committees` is "not asked for: " + `WEB_HELD_SAID`, which does not count as `bad` (`6016`).
  - The weekly never knocks. The night does that four hours later.
- **The laptop.** Its own records stay a person's for the web server. The night never knocks them, though the night still uses the database under a laptop drop record. Hand fetches keep their 24 hours (`refusal.py:211-220`). The lane keeps "any record".
- **A New term run under a resumable hold.**
  - If due, it knocks: it is `main` and not dry.
  - If not due, it stops before asking and says how to clear the hold or when the knock comes. It never uses the database (`nightly.py:3006-3010`).

---

## 3. What the page, the verdict and the alerts say

Every sentence is the project's own and carries none of the server's words. The run's page is public (`nightly.py` `take_documents` docstring; `page_quote`, `2678-2685`).

### 3.1 The verdict (`archive/last-night.json`)

- **`fetch`** stays the truth about the export:
  - `"refused"` on the night of the drops;
  - `"held: the General Court's web server dropped the night's connections on 2026-10-29 at 08:27 UTC; not asked tonight"` on a held night;
  - as today otherwise.
- **`files_from`**: `"database"`.
- **`day_files.because`**: `"the web server dropped two connections"`, or `"the web server is held after dropped connections since 2026-10-29"`. It is `"the export came back empty"` only when that is what happened.
- **`web`** is new. For example:
  `{"state": "clear"|"held"|"lifted"|"person", "kind": "dropped", "since": "2026-10-29T08:27:15Z", "machine": "github", "rung": 1, "knocks": [{"at": "2026-10-30T08:23:40Z", "answer": "dropped"}], "next": "2026-11-01T00:23:40Z", "lifted": null}`
- **`tried`**, in order. For example:
  - the night of the drops: `["the export, try 1: refused", "the database: all seven of the day's changing files installed"]`;
  - a held night: `["the web server: held after dropped connections on 29 October; not asked tonight, and asked once from 1 November", "the database: all seven ..."]`;
  - a lift night: `["the web server: one request for downloads/Members.txt answered whole (82,694 bytes); the hold of 29 October is lifted", "the export, try 1: installed"]`.

### 3.2 The run's page: warnings

All of these are kinds that never hold the gate.

1. `KIND_FROM_DB` (unchanged constant, new sentence): "the day's files were built from the General Court's database, because its web server dropped two connections at 08:27 UTC" / "... because its web server is held after dropped connections on 29 October (night 3 in a row)".
2. `KIND_WEB_HELD` (new, in `KINDS_FALLBACK`): "the General Court's web server is held after dropped connections: nothing is asked of it until one test request at about 08:20 UTC on 30 October".
3. The bill requests and the lists: "next session's bill requests: not asked for: the General Court's web server is held after dropped connections; the earlier 312 kept". These are exempt like the clock's (`clock_kind` on night-clock), by a new `held_kind()`.
4. `KIND_WEB_LIFTED` (new, in `KINDS_FALLBACK`), on a lift night: "the General Court's web server, held since it dropped two connections on 29 October, answered the night's one test request: the night lifted the hold and asked the export as usual".

If these were not exempt, the first database night after a drop would be held by "a new warning kind" (`warning_reasons`, `nightly.py:4819-4844`). That is the night of 1 October again, in another form.

### 3.3 `plain_why` (not clean only)

- **Refused, a person's** (`2283-2285`): "The General Court refused a request (a refusal only a person may lift). Nothing more was asked, its database included. Nothing was published."
- **Held, and the database gave nothing:** "The General Court's web server is held after dropped connections, and its database did not give the day's files either (`DB_WHY[...]`), so nothing was installed or built. The night tests the web server again at about 08:20 UTC on 1 November. Nothing was published."
- **Knock refused:** "The night's one test request of the General Court's web server met the firewall's block page, so the hold is a person's now and nothing more was asked, its database included. Nothing was published."

### 3.4 Alerts (`alerts_of`, `5750-5777`) and warns (`warns_of`, `5739-5747`)

- **Warns** (resumable, 0–1 failed knocks): "The General Court's web server dropped the night's connections on 29 October at 08:27 UTC and is held. The site is built from its database meanwhile and published as usual. The night asks the web server once at about 08:20 UTC on 30 October and lifts the hold itself if it answers; a refusal leaves it for a person."
- **Alert** (2–3 failed knocks): "The General Court's web server has not answered since 29 October: 2 test requests, on 30 October and 1 November, were dropped. The site is still built from its database. The next test is at about 08:20 UTC on 5 November, and after 4 that fail the hold is a person's. A person may run python3 netcheck.py on the laptop and write to the General Court's IT office."
- **Alert** (a person's, any cause): today's sentence (`5761-5763`), saying what made it a person's: "a 403", "the firewall's block page", "4 test requests dropped", "a record with no kind". For a `dropped` record it adds: "The site is still built from its database."

---

## 4. 29 October under this design

All times UTC. The facts are from the log, the verdict and the bucket; the design's steps are marked.

| When | What |
|---|---|
| 08:21:13 | `nightly.py --runner` starts; preflight takes 356 s |
| ~08:27:08 | `gc_quiet()` and `db_quiet()` are true; there is no record |
| ~08:27:08–14 | The page drops, then `Docket.txt` drops. **`note(kind="dropped", machine="github", ref=main, dry=false, rung=0)`**. Snapshot exit 2 |
| ~08:27:15 | **The loop sees `refused` with an open database door and calls `from_database()` once.** `fetch_day_db.py` makes 11 connections, `PAUSE = 4.0` s apart (`fetch_day_db.py:96`). On the five October database nights this installed every time |
| then | The study views and term data come from the database. The bill requests and lists are **not asked for: held**. The what-changed report is written with `--db-night`, then the build (under 30 minutes, `nightly.yml:435-436`), `check_site` and the census |
| then | Gate: `KIND_FROM_DB`, `KIND_WEB_HELD` and the held lists never hold it. Publishable unless production already serves it, a release lacks its dry-run proof, or a "hold"-tier check fails |
| after exit | "A refusal goes to R2 at once" puts `state/refused.json` (kind dropped) in the bucket. The warnings' check gets the warn line |
| 30 Oct 08:17 | The timer starts the night; state-down brings the record down; preflight runs |
| ~08:23 | The record is 23.9 h old, past 16 h, and inside 08:00–12:00. **The knock**: one GET of `downloads/Members.txt` |
| — if answered | The record is moved aside and `refusal-lifted.json` written; the export runs as on any night; at the step-13 `state_up`, `lift_in_bucket` moves `state/refused.json` to `replaced/2026-10-30/lifted/` |
| — if dropped | `rung` 1, next knock due 1 Nov 00:23; a database night. Day 2 of a stale site: **none** |

**The site under each design:**

| | Stale days | General Court web requests after the drops | Who must act |
|---|---|---|---|
| Today | until a person acts | 0, and then netcheck's 8 when a person comes | a person |
| This design | **0** | **1** on 30 Oct (then 0 or the normal night) | nobody, unless the knock is refused or 2 knocks fail |

---

## 5. Code changes

**Build order.**
1. `feat/night-clock` must be merged first: `asking_left`, `seconds_left`, `run(timeout=)`, `RUN_KILLED`.
2. **Phase 1** (the biggest value, smallest change): the kinds, the database door, the page and alerts.
3. **Phase 2**: the knock and the lift.

Phase 1 alone ends the stale site. Phase 2 ends the person's chore for drop-kind holds. Phases may ship together if the owner prefers.

| File | Change | Phase |
|---|---|---|
| `refusal.py` | `note(where, why, kind=None, retry_after=None)` writes `kind, machine, ref, dry, run_id, id, since, rung, knocks`, with lift memory (§2.5). New `record_kind(err, body)` splits 503 out as `unavailable`. `RESUMABLE = ("dropped", "unavailable")`, `db_door(d=None)`, `KNOCK_HOURS = (16, 40, 88, 160)`, `KNOCKS_MOST = 4`, `RETRY_AFTER_MOST_HOURS = 168`, `LIFT_MEMORY_DAYS = 14`, `LIFTED`, `LIFTED_DIR`, `knock_due(d=None, now=None)`, `knocked(answer, said, now=None)` (the one writer of rewrite, lift and person), `held_said(d)`. `check(who, knock=False)`. `force()` (`195-208`) and `main()`'s status (`861-867`) state the kind and the next knock. The docstring section A HOLD THAT TESTS ITSELF | 1 (kinds, door); 2 (knock) |
| `src/fetch/gc_web/snapshot_gencourt.py` | `read_one()` returns the HTTP status and `Retry-After` beside its kind. The three `note()` calls pass `kind=refusal.record_kind(...)`: `:585` refused, `:615` refused or unavailable, `:621` dropped. `--knock` with `knock()`, `KNOCK = EXTRA[0]`, `KNOCK_TIMEOUT = 60`: `check(knock=True)`, `hold("the knock")`, the write-first `knocking` mark, one `read_one`, `refusal.knocked()`, exit 0/1/2. `:683` says what the record now does, not "for a day" | 1; 2 |
| `src/fetch/gc_web/fetch_committees.py` | `:234`: `note(..., kind=refusal.record_kind(e))` | 1 |
| `nightly.py` | `db_quiet()` beside `gc_quiet()`, whose `why` names the kind. The fetch block (`1541-1706`): both doors, the loop's break (`1587-1589`), `last = tries` on a refusal, the held path that asks no export, gates `1626/1636/1645` on the database door and `1641/1653` on no record. `from_database(..., because=)` with its gate at `3011-3015` on `db_door()`. `WEB_HELD_SAID`, `held_kind()`, `KIND_WEB_HELD`, `KIND_WEB_LIFTED` (both in `KINDS_FALLBACK`, `946`). `warned()` (`5259-`): the cause in `KIND_FROM_DB`'s sentence and the held/lifted lines. `warning_reasons()` exempts `held_kind`. `plain_why()` (`2256-2359`): "held" and kind-aware "refused". `alerts_of`/`warns_of` (§3.4). `alarms()` (`5381`) generalised. The verdict's `web`. `weekly()` (`5981-6020`) with both doors. Phase 2: `KNOCK_MINUTES = 2`, `knock_web(night)` gated by `asking_left`, killed by `run(timeout=)`, with `RUN_KILLED` turned into `knocked("dropped")`. Docstrings (§7) | 1; 2 |
| `src/ops/cloud.py` | `state_up()` (`1627`) runs `lift_in_bucket()` first (compare-and-move, §2.5); `DRY_NEVER` (`457`) gains `refusal-lifted.json`; `pull_refusal()` (`2754`) sets aside a lifted laptop copy; `send_refusal()` (`2137`) never sends a lifted `id`; docstrings `1637-1640`, `2049-2061`, `2754-2771` | 2 |
| `cloud_kit.json` | the state entry for `archive/refusal-lifted.json`; the `what` of refused.json (`197-198`); `dry_run.what` says the lift never travels | 2 |
| `.github/workflows/nightly.yml` | step "A refusal goes to R2 at once" (`447-459`): `if` also on `archive/refusal-lifted.json`, and its name | 2 |
| `src/fetch/gc_db/fetch_day_db.py`, `src/fetch/gc_db/probe_db.py` | docstrings only (§7) | 1 |
| `.claude/hooks/guard.py` (`302-306`) | `cloud.py clear-refusal` and `send-refusal` ask first, like `refusal.py --clear`. **Configuration: the owner's decision (D8)** | either |
| `versions.json` and each file's stamp | `python3 src/ops/inventory.py --bump-changed` | both |

**Not changed:**
- `classify()`;
- the snapshot's two-drop rule and its page-counts-as-first (§8 R10);
- `netcheck.py`;
- the lane;
- the gate's other reasons;
- `TRIES_AFTER_DB` on an unheld night;
- `DB_AFTER_TRIES = 1`;
- the timer;
- `started`.

---

## 6. Checks: each fails if its rule is removed

`preflight.py --code`, no network, with fakes in a throwaway folder, in the style of `_nightly_falls_back` (`preflight.py:89426-`).

| # | Rule | Check and assertion | Removing the rule makes it fail because |
|---|---|---|---|
| C1 | A record carries its kind and who wrote it | new `_refusal_kinds`. With `GITHUB_ACTIONS=true`, `GITHUB_REF=refs/heads/main` and `DRY_RUN` unset, `note("x","y",kind="dropped")` writes `kind`, `machine=="github"`, `dry is False`, `rung==0`, `id` | `note()` writing `{at,epoch,where,why}` alone fails the field asserts |
| C2 | No kind is a person's, at any age | same check: `{"epoch":0,"where":"old"}` gives `db_door` False and `knock_due` False at `now = 10**10` | treating a missing kind as resumable flips both |
| C3 | `refused` is a person's | `kind:"refused"`, any age: both False | — |
| C4 | Only GitHub's own `main` records are knocked | `dropped` with `machine:"laptop"`: `db_door` True, `knock_due` False at any age; `dry:true`: False; `ref:"refs/heads/dev"`: False | dropping the machine, dry or ref test makes `knock_due` True |
| C5 | The ladder | `KNOCK_HOURS == (16,40,88,160)`, `KNOCKS_MOST == 4`; `knock_due` False at +15.99 h, True at +16 h; after `knocked("dropped")` False at +39.9 h, True at +40 h; after 4 `person` is True, `knock_due` False for ever, `db_door` still True | pins each number and the "four, then a person's" |
| C6 | 503 waits for Retry-After | `note(kind="unavailable", retry_after=30*3600)`: False at +16 h, True at +30 h; `record_kind` of `HTTPError(503)` is `unavailable`, of 429 is `refused`, of 403-with-Retry-After is `refused` | treating 503 as `refused`, or ignoring Retry-After |
| C7 | A lift is a move, never a delete | `knocked(None, ...)`: MARK gone; `LIFTED_DIR/<id>.json` byte-for-byte the old record; `LIFTED` names `id` and carries the record; the file count under `archive/` is unchanged plus one | `MARK.unlink()` fails the aside assert |
| C8 | A knock refused is a person's | `knocked("refused", "block page")`: `kind=="refused"`, `person`, `db_door` False | — |
| C9 | Lift memory | a `dropped` note 1 day after a lift of rung 2 gives `rung == 3` and the lifted `since` | a fresh ladder every day |
| C10 | `check(knock=True)` lets only a due knock through, and hand fetches keep 24 h | a due record (17 h): `check(knock=True)` returns and `check()` exits 2; a non-due record: `check(knock=True)` exits 2 | — |
| C11 | The snapshot writes the kind | extend `_snapshot_stops` (`81515`): two drops give `kind=="dropped"`; a 403 gives `refused`; a 503 with Retry-After gives `unavailable` and `retry_after_until`; the block page gives `refused` | `:621` without `kind` |
| C12 | The knock asks exactly one URL, and never the data page | drive `snapshot_gencourt.py --knock` with `get` faked: `calls == [EXTRA[0][0]]`, `PAGE` not asked, the UA is `UA`; data gives exit 0 and a lift; a drop gives exit 1 and `rung+1`; the block page gives exit 2 and a person's; the `knocking` mark is written before the call | a second URL, the page, or a browser UA |
| C13 | The night of the drops goes to the database at once, and asks the web server nothing more | `_nightly_falls_back` new run **311d**: `refuse_on=1` writing `kind:"dropped"` gives `order()==[SNAP, DBASK]`, `slept==[]`, `fetch=="refused"`, `files_from=="database"`, clean, publishable, `tried==["the export, try 1: refused", "the database: all seven ..."]`, no `fetch_lsrs.py` or `fetch_calendar_archive.py` call, `fetch_archive_db.py` called | the break at `1587-1589` unchanged stops before `DBASK`; asking the lists under a hold puts them in `calls` |
| C14 | The database night under a hold publishes without approval | same run: `NI.warning_reasons(warned, served=set(), recent=())==[]` | `KIND_WEB_HELD` missing from `KINDS_FALLBACK`, or `held_kind` not exempt |
| C15 | Held and not due: no web request at all | run **310d**: a `dropped` github record 1 h old gives no `SNAP`, no `KNOCK`, one `DBASK`, installed, `fetch.startswith("held")` | the held path asking the export |
| C16 | Kindless records keep today's behaviour | runs 310, 311, 311b, 317 and the direct `from_database()` call (`preflight.py:90012-90130`) **unchanged** and green; plus `from_database()` with a `dropped` record asks | — |
| C17 | Due: one knock, then the export | run **310k**: a 17 h record with the knock faked as answered gives `order()==[KNOCK, SNAP]`, no `DBASK`, MARK gone, LIFTED written | the knock not wired, or the export asked first |
| C18 | Knock dropped: the database, not the export | run **310kd**: `order()==[KNOCK, DBASK]`, record `rung==1` | — |
| C19 | Knock refused: nothing more | run **310kr**: `order()==[KNOCK]`, not clean, alert line present | — |
| C20 | No knock on a dry run, nor outside the clock | run **310dry** (`--dry-run`, due record): no `KNOCK`; run **310late** (`GRANITE_CLOCK_UTC` 12:30): no `KNOCK`, `web.knock.startswith("not asked for: it is 12:30 UTC")`, `DBASK` once | — |
| C21 | `asking_left` now gates three steps | night-clock `_night_clock`'s `gated == ["knock_web", "take_documents", "take_lsrs"]`, and its docstring sentence updated | — |
| C22 | The bucket lift is compare-and-move, and never on a dry night | new `_cloud_lift` in `_cloud_state_and_site` (`55276`), folder bucket. `state/refused.json` = R (id i), the state record names `sha(R)`, local LIFTED names i, then `state_up`: refused gone, `replaced/<day>/lifted/refused.json == R`, `state/refusal-lifted.json` present; a second `state_up` changes nothing; with `only=dry_run.state`: nothing moved, nothing sent; with a bucket holding R' (another id or another sha): nothing moved; `"refusal-lifted.json" in CL.DRY_NEVER` | — |
| C23 | A lift is not undone by the laptop | `_cloud_pull` (`58726`): laptop holds R, bucket none, LIFTED names i: no failure, R under `set-aside/<day>/`; `send_refusal` returns done and the bucket is still empty | — |
| C24 | Escalation reaches the right check | extend `_alarm_stays_able_to_ring` (`109839`): `rung` 0–1 resumable puts the line in `warns_of` and not `alerts_of`; `rung` 2 puts it in `alerts_of`; `person` puts it in `alerts_of`; kindless puts it in `alerts_of` | — |
| C25 | The weekly under a hold | weekly fixture: a `dropped` record, the four database pieces asked, `fetch_committees.py` not asked, clean | — |
| C26 | The workflow carries a lift at once | a text check of `nightly.yml`: the refusal step's `if` names both files | — |
| C27 | (D8) the guard | `_assistant_guard` (`67182`) rows: `cloud.py clear-refusal` and `cloud.py send-refusal` give `ask` | — |

The rows marked — fail by their own assertion when the rule they pin is removed.

---

## 7. Docs, and the CLAUDE.md paragraph

**The CLAUDE.md paragraph.** It is edited only with the owner's word. It replaces `CLAUDE.md:74-79`, which is already wrong twice: the lane holds at any age, not 24 h, and `refusal.py:22-24` says fifty-four seconds, not twelve.

> **A refusal outlives the run that met it.** `refusal.py` records one in `archive/refused.json`, with its kind. It exists because a drain that met two 403s stopped itself correctly, and a chained run started asking the same address for a docket fifty-four seconds later. A 403, a 429, the firewall's block page, or a record with no kind holds every fetch, the General Court's database included, until a person clears it: `python3 refusal.py --clear` here and `python3 src/ops/cloud.py clear-refusal` for the bucket, after `netcheck.py` has said what kind it was. Two dropped connections or a 503 that GitHub's night meets are an outage until shown otherwise: that night and the ones after build the day from the General Court's database and ask its web server nothing, and the night alone asks it one request, for `downloads/Members.txt`, the next morning and then 2, 4 and 7 days on, between 08:00 and 12:00 UTC. An answer lifts the hold, a refusal makes it a person's, and so do four that fail (the person's approval, <date>). Hand fetches here still stop for 24 hours, and the lane at any record.

**Other docs that change.**

| Doc | Lines | What changes |
|---|---|---|
| `refusal.py` docstring | `35-38` ("Nothing clears it automatically") | a new section, A HOLD THAT TESTS ITSELF; the kinds; why `dropped` is not "wait a bit" |
| `refusal.py` `force()` and `main()` | `195-208`, `861-867` | the kind, and the next knock |
| `nightly.py` docstring | `26-30` ("a refusal on file, at any age, means no fetch tonight") | "a refusal a person must lift..."; a held web server asks the database |
| `nightly.py` docstring | `313-320` (the `when` row) | "no refusal a person must lift"; at once after the drops |
| `nightly.py` | new section A NIGHT THE WEB SERVER DROPS US (date) | the doors, the knock, the page |
| `nightly.py` | `1705-1706`, `2283-2285`, `5758-5763`, `6013` | kind-aware sentences |
| `nightly.py` | `1078-1084` and `5381-5385` (`DB_NIGHTS_MOST`) | the cause generalised |
| `nightly.py` (night-clock) | THE NIGHT'S CLOCK | "those two steps" becomes three, with the knock first |
| `snapshot_gencourt.py` | `683` | "holds every fetch for a day" is wrong for the night today, and is replaced |
| `fetch_day_db.py` | `21-24`, `63-66` | "with no refusal a person must lift" |
| `probe_db.py` | `84-89`, `109-110` | "where only a person clears a refusal" becomes "a refusal; a dropped-connection hold is tested once a rung" |
| `cloud.py` | `1637-1640`, `2049-2061`, `2754-2771` | the night's lift |
| `cloud_kit.json` | `197-198`; the new entry; `dry_run.what` | — |
| `ARCHITECTURE.md` | `113-117` | the fetch, held |
| `ARCHITECTURE.md` | `266-272` | "a refusal held for three nights is one email and its recovery is the sign it was cleared" becomes "...cleared, or lifted by the night". Separately, that sentence still lists "a night the gate holds for approval" among alerts, which `nightly.py:5707-5715` moved to the warnings on 22 Oct: existing drift |
| `CONTRIBUTING.md` | `24-31` | — |
| `README.md` | `344-353` | — |
| `SECURITY.md` | `93-98` | — |
| `watchers/README.md` | `71-83` | `pull` sets aside a lifted record |

---

## 8. Risks

1. **A drop may be a real block.** The only first-hand description of a block is drops on everything (`netcheck.py:11-19`). The 29 October drops look the same on the wire.
   - Bounds: one request a rung, at most four over 14 days. Only from the night's job, under its lock, inside 08:00–12:00 UTC. Never on the run that met the drops. A refused answer ends it.
   - *Guess:* whether their firewall lengthens a block for one request a few days apart. Both recorded blocks followed hundreds of requests, or two workers at once (`read_history.md` §3A).
2. **The database during a block disguised as drops.** The night keeps reading about 170,000 rows a night from PublicSQL. The IT office okayed that host "during a session", and `probe_db`'s hold stops it after one failed connection. *Guess:* whether the SQL host sits behind the same perimeter.
3. **Guards compare the database with itself.** After a run of database nights, the guards compare the database's files with the database's own, and only the export would catch a systematic difference (`nightly.py:2607-2609`). Bounded by `DB_NIGHTS_MOST` (7) on the page, the night's alert from the second failed knock, and a person's hold at the fourth.
4. **The lift and the bucket.**
   - If a lift does not reach the bucket (a killed job, an R2 error), the record stays and the night knocks again when due. That is conservative.
   - If the bucket changed since state-down, nothing is moved.
   - *Not covered:* a laptop refusal waiting behind the night's record (the unsent marker) loses its place when the night lifts, as it does under `clear-refusal` today. `pull` reports it as a failure (`cloud.py:2857-2859`).
5. **Healthchecks visibility.** The first rung goes to the warnings' check, which may already be down: it has been, for the captions inbox, since 25 October. Then the person hears nothing until the second failed knock, about three days in. This is owner decision D5.
6. **Records written before the change have no kind.** That includes the one in the bucket now (175 bytes, `where: snapshot_gencourt`). Each stays a person's: **the standing 29 October record must be cleared by a person**. This design does not lift it.
7. **Dry runs.** They cannot exercise the knock or the lift, by design. The first real knock is on `main`. The preflight fakes (C12, C17-C20, C22) are the proof. A dry run does exercise the database door.
8. **The approval gate still applies.** A release without its 48 h dry-run proof (`nightly.py:4583-4603`) still waits. Daily database nights keep each night's change small, so the 600-row reason (`872`) is not tripped by a backlog.
9. **`Members.txt` as the knock.** If it moves (404), every knock fails and the hold is a person's in 14 days, while the export also fails "did not complete". If `/downloads/` answers while `/dynamicdatadump/` drops, lift memory bounds a flapping night to 3 requests.
10. **The snapshot still stops at its second request when the page drops** (`snapshot_gencourt.py:587-588`). Under this design that stop costs no stale day, so it is left alone. Making the snapshot more persistent would add requests on a bad morning.
11. **The night-clock merge is a precondition.** Phase 2 cannot ship before it.
12. **The new term (2 December) under a hold.** The database guards stop a turn, and a New term run needs the web server: a person is needed for it anyway (`read_holds.md` rank 2).
13. **The weekly's committee rooms and the lookups age while held.** These are warnings, and are in the alarm's sentence at 7 nights.
14. *Guess:* GitHub runners' addresses differ night to night. If so, a record is about yesterday's address, and the knock tests the address that will actually fetch, which is the right test. Nothing in the repository records a runner's address.

---

## 9. The owner's idea, weighed

The owner asked: "the live updates may assist in that regard since presumably they'd be more frequent and lightweight pings that the nightly can resume whenever the live shows it's up again".

**What it cannot do, as designed.** The live Worker cannot show that the web server is back:
- **It never asks gc.nh.gov.** "What it never does: ask gc.nh.gov" (`design_final.md:59-60`; §6.1, `:743`).
- **It reads PublicSQL only Hot, Warm, or on a Heartbeat.** The Heartbeat runs on weekdays from 1 January to 30 June and in the 14 days after a sitting. It is Off otherwise (`design_final.md:341-346`), and it never starts inside the night's window (`:374`). **On 29 October it would have read nothing.**
- **It reads from Cloudflare's addresses**, a third network that says nothing about GitHub's runner. A knock from the Worker would be a second machine asking beside the night, which is the pattern behind the second block (CLAUDE.md).
- **It writes its own bucket** (`design_final.md` §3.1). The night holds no credentials for it (`nightly.yml:334-337`).
- **Its SQL half is unbuilt.** `live/tds` is marked WIP and waits on the November test (`design_final.md` §2.7).

**Where the idea is right, and what this design takes from it.**
1. **"Frequent, lightweight pings decide when the heavy job resumes."** This is exactly the knock's shape. It is moved to the one place where it proves something: one light request, from the machine and address that will fetch, under the night's lock, seconds before the export.
2. **"The live layer's door is healthy when the website is not."** That door, PublicSQL, is this design's main part. The night uses it itself, the same morning, so the site stays current before the web server's question is even asked. The live Worker's own failure rules already follow the same self-expiring pattern (`design_final.md:436-445`, "None needs a person to clear it").
3. **During a sitting, the live votes keep `/session/<B>/today` current between nights** (`design_final.md` §4.2), whatever the night's web server does. On session days, readers see the day's roll calls even on a morning the website is out.
4. **A later, optional diagnostic, not a decision** (not proposed for building now). Say the night's database connection fails while the Worker's `state.json` shows PublicSQL answering Cloudflare minutes earlier. That says GitHub's path is the problem, not the host. It would need the night to read the live bucket, which is a new secret and a new coupling.

---

## 10. Decisions for the owner

| # | Decision | Recommended |
|---|---|---|
| D1 | **The database is the night's source while the web server is held after dropped connections or a 503**, at once on the night it happens. This changes "carrying on by another door is a person's decision" (`nightly.py:3011-3015`; preflight runs 310, 311 and 317 stay as they are for kindless records). The evidence for it: the IT office's "No problem hitting PublicSQL during a session as it doesn't touch the website", `probe_db.py:109-110`, and 7 of 7 database nights whole in October | **yes** |
| D2 | Whether the database stays **closed** under a 403, a 429 or the block page | **closed**. A true block is the case that ends in an email to a Clerk's office, and the person should be able to say nothing of theirs has been asked since. 429 is a complaint about our rate |
| D3 | The night tests and lifts a drop or 503 hold by itself: one request for `downloads/Members.txt`, rungs 16/40/88/160 h, at most 4, inside 08:00–12:00 UTC, `main` only, never a dry run, never a laptop's record | **yes**, as phase 2 |
| D4 | 503 is resumable, honouring Retry-After; 429 stays a person's | **yes** |
| D5 | Where the first notice goes | the warnings' check for 0–1 failed knocks, the night's check from 2. **Or** the night's check from the start, if the owner would rather hear on day 0 |
| D6 | `pull` sets aside the laptop's copy of a lifted record, rather than keeping it and reporting it | **set aside** |
| D7 | The CLAUDE.md paragraph in §7 | — |
| D8 | The guard asks before `cloud.py clear-refusal` and `send-refusal`, as it does before `refusal.py --clear` (`.claude/hooks/guard.py:302-306`) | **yes** |
| D9 | The record standing now (29 Oct, no kind) is cleared by a person, after `netcheck.py`. This design never lifts a kindless record | — |

---

## 11. Effort (a guess)

**Code.** About 700 lines (each a guess):

| File | Lines |
|---|---|
| `refusal.py` | about 180 |
| `snapshot_gencourt.py` | about 80 |
| `nightly.py`, with docstrings | about 260 |
| `cloud.py` | about 130 |
| `cloud_kit.json` and the workflow | a few |

**preflight.** About 700–900 lines across C1–C27, in its existing style. That is the bulk.

**Process.**
- Phase 1 is one working session for the code and checks, plus a review round and a dry run on dev. The dry run exercises the database door, but only with a record placed by hand in a scratch bucket, since a dry run sends `refused.json` back.
- Phase 2 is a second session plus a review. Its first real exercise is `main`'s night.
- Each full `preflight.py --code` run is 3–4 minutes (`CLAUDE.md`, measured 23 October).

---

## 12. Said plainly as guesses

- The rung hours (16/40/88/160), `KNOCKS_MOST = 4` and `LIFT_MEMORY_DAYS = 14` are my numbers, built on `probe_db`'s pattern. None is measured against gc.nh.gov.
- That `downloads/Members.txt` is served by the same front door as the data page, and that it is static.
- That a firewall does not lengthen a block for one request a few days apart.
- That the SQL host does or does not sit behind the same perimeter as the website.
- That GitHub runners' outbound addresses change from night to night.
- That some firewalls answer a block with a 503.
- How long each phase takes.
