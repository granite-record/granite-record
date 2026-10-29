# The night that heals itself: the method to build

Final design, 29 October 2026, revised the same day after the red team (§17). This is read-only work. Nothing asked the General Court, its SQL host or YouTube, and nothing tracked was edited.

**Code read.**
- `dev` = `origin/dev` = `4590795`: `0702100` plus one How to Vote text commit (3 files, none of them below).
- `origin/feat/night-clock` = `22d19e4`: `84a81ee` plus `f48edfe` (a reading between 12:00 and 13:30 UTC says "outside the hours"), a merge of dev, and stamps. Line numbers marked **nc** are that branch's. Bare ones are dev's.
- `feat/night-documents` (`c5e179f`, unmerged), for one precedent (§13).

**Evidence.**
- Run 151's log, verdict and refusal record from the bucket (already in `r2/`).
- The 30 main night logs from 30 September to 29 October, read from the bucket for the red team round and deleted afterwards.
- The four readers, the three designs and the two judges in this folder.

**"Guess"** marks anything the code, the logs or the history do not show.

---

## 0. On one page

**The method.** A refusal record says what kind it was. Two kinds are *the night's to test*, when GitHub's own night on `main` (not a dry run) met them:
- two dropped connections or timeouts ("dropped");
- an HTTP 503 whose body is not the firewall's page ("unavailable").

The night tests a record only while the switch is on **and** the third Healthchecks check exists (§2.9, §2.11). That check is the one that emails the person when a record becomes theirs. Without it the method stays off, so that email can never be lost.

While the night tests a record, three things happen.
1. **The website is asked nothing**, except the knock.
2. **The knock.** One GET of `https://gc.nh.gov/dynamicdatadump/Counties.txt` (195 bytes, a file the night asks for every night). It goes out from inside the night's own job and lock, only between 08:00 and 11:18 UTC:
   - the first comes on the next morning;
   - if needed, the others come 2, 4 and 7 days after the one before (on 29 October's dates: 30 Oct, 1, 5 and 12 Nov).
   - Any answer from the server that is the file lifts the record. That means a 200 that is not the firewall's page and not a web page, **whatever its size**. The record is moved aside, the lift is written into the bucket, and the night carries on as any night.
3. **The site is built from the General Court's database** (PublicSQL, the host its IT office said is fine to ask) on every night the record is still being tested. This uses the existing `from_database()` with every guard it has. It needs the owner's word, because it changes "carrying on by another door is a person's decision".

**One door.** The knock and the database are open exactly while the night tests the record. The night stops testing after a fourth unanswered knock, after 16 days, or on any block-type answer. The record is then a person's: both close, and the third check emails.

**What does not change.**
- The night that meets the drops ends as today: nothing more is asked, nothing is built, and the record goes to the bucket within seconds (§2.2, rule A).
- Everything else stays a person's, as today:
  - a 403, a 429, the firewall's page or a redirect, on the night or on the knock;
  - anything met on the laptop or by a dry run;
  - every record written before this change, the one standing now included.
- `classify()`, the lane, the approval gate.
- The two-drop rule, except in the week after a lift: then the export stops at its first drop (§2.7).

**29 October under it.**
- 08:27 UTC: two drops, a record of kind `dropped`, sent to R2 at once. Nothing built. One email, from the night's check.
- 30 October, about 08:23 UTC: one knock.
  - If answered: the export, the build and the publish, as on 28 October, about 09:30 UTC.
  - If not: a database night, published about 09:30 UTC; knocks on 1, 5 and 12 November.
- Either way the site is about one day behind, not behind until a person acts.

| | |
|---|---|
| New scripts, machines | none |
| New secret | one: `HEALTHCHECKS_PERSON_URL`, the third Healthchecks check, which the owner creates (D5) |
| New state file | `archive/knocks.json` (R2 `state/knocks.json`) |
| Workflow change | two lines in the workflow-level `env` of each of `nightly.yml` and `weekly.yml`: `NIGHT_KNOCK` (the off switch) and `NIGHT_PERSON_CHECK` (whether the third check is set). In `nightly.yml`, the existing "Tell Healthchecks how the night ended" step also pings the third check. No new step, and no `if` changes |
| Web requests the knock can add | at most 1 a UTC day, at most 4 per outage |
| Depends on | `feat/night-clock` (`asking_left`, `seconds_left`, `run(timeout=)`). Built on it, landed after it |

**The owner's decisions** (for_owner.md puts them in plain words):

| # | Decision | Recommended |
|---|---|---|
| D1 | Clear the standing 29 October record by hand now (§8 step 1). It has no kind, so nothing here will lift it | yes, now |
| D2 | The rule itself: the night tests and lifts a drop-type record its own main night wrote. This changes `refusal.py:35-38` ("Nothing clears it automatically"), the night's "a refusal on file, at any age, means no fetch tonight (a run nobody watches does not decide a refusal is over)" (dev `nightly.py:27-29`) and CLAUDE.md:74-79. It needs the owner's OK by their standing rule | yes |
| D3 | The database while the night tests the record, for 16 days at most. This changes "carrying on by another door is a person's decision" (dev `3011-3015`; `fetch_day_db.py:63-66`) and answers dev `2600-2610`'s "a person's decision". The database closes whenever the record is a person's, for any reason | yes. If no: commit 7 is left out |
| D4 | A 503 without the block page is resumable. It is never tested before its `Retry-After`, and one over 160 h is a person's. A 429 stays a person's (§2.8) | yes |
| D5 | Create the third Healthchecks check ("a refusal is yours") and store its ping URL as the repository secret `HEALTHCHECKS_PERSON_URL`. The method is off until it exists | yes, before the merge to main |
| D6 | The guard asks before `cloud.py clear-refusal`, `send-refusal` and `netcheck.py` (configuration); netcheck's verdict is fixed; the CLAUDE.md paragraph of §7 | yes |

---

## 1. What the code does today, and where it stops

| Step | Today | Where |
|---|---|---|
| The record | `{at, epoch, where, why}`. No kind, machine, branch or dry-run flag | `refusal.py:113-127` |
| The incident | The page's drop counts as the first of two (`snapshot_gencourt.py:587-588`). `Docket.txt`'s drop is the second, so `note()` fires (`:618-621`) and the file's 60 s retry (`:624-630`) is never reached | log lines 1656-1668 |
| To the bucket | Only after `nightly.py` exits, in "A refusal goes to R2 at once" | `nightly.yml:447-459` |
| Later nights | `gc_quiet()` is false at any record of any age | dev `1233-1246` (nc `1308-1321`) |
| The database | The loop breaks on anything but "empty". `from_database()` refuses with any record on file ("carrying on by another door is a person's decision"). The study views, term data and statutes need no record on file | dev `1587-1589`, `3011-3015`, `1626-1653` (nc `1662-1664`, `3086-3090`, `1701-1728`) |
| The weekly | Defers everything, its database pieces included | dev `5981` (nc `6141`) |
| The bucket | `state_up` never removes a file. Only `clear-refusal`, by hand, moves `state/refused.json`, and records "cleared" only on the machine that ran it | `cloud.py:1637-1640`, `2049-2112` |
| The laptop | A copy the bucket lacks makes `pull` FAIL while under 24 h. An older one gets the advice "send-refusal sends it if it should stop the night too" | `cloud.py:2801-2813` |
| The lane | Stops at any `archive/refused.json`, and writes only to its own log. It cannot ask again until a person runs `pull` ("reading the bucket is a person's command here, not the lane's") | `gc_lane.py:402-406`, `46-54`; `refusal.py:730-744` |
| Healthchecks | Emails only when a check changes state ("a refusal held for three nights is one email"). A night with an alarm is not clean, and a night not clean sends `/fail` | dev `5683-5690` (nc `5846-5849`); nc `5583`, `5935`; nc `nightly.yml:586-596` |
| Precedent | The SQL host's own hold expires by itself (20/44/92/164 h), "the deliberate difference from the web server's rule ... a month unattended needs it" | `probe_db.py:73-115` |

---

## 2. The method

### 2.1 The record says what it was

`refusal.note(where, why, kind=None, retry_after=None)` writes `archive/refused.json` **once**, as today, with these fields added:

| Field | Value |
|---|---|
| `kind` | `"dropped"`, `"unavailable"`, `"refused"`, or absent |
| `machine` | `"github"` when `GITHUB_ACTIONS == "true"`, else `"laptop"` |
| `ref` | `GITHUB_REF` (exact, case-sensitive, as `nightly.MAIN_REF` reads it) |
| `dry` | true when `DRY_RUN == "true"` or `ref != "refs/heads/main"` |
| `run_id` | `GITHUB_RUN_ID` |
| `retry_after` | seconds, only for "unavailable" when the server named them |

**Who passes a kind.** Only the snapshot's three `note()` sites (`snapshot_gencourt.py:585`, `:615`, `:621`) and `fetch_committees.py`'s two (`:235`, `:241`). The other `note()` call sites (55 in all, per read_night) pass none. A record with no kind is a person's at any age.

`refused.json` is never rewritten after `note()`. All knock state lives in `knocks.json` (§2.6), so every comparison by sha in `cloud.py` keeps working unchanged.

### 2.2 Whose a record is: one rule, one answer, both doors

`refusal.whose(d=None, k=None, now=None)` returns `("night" | "person", why)`. It is the only reader of this rule. `d` is `refused.json`. `k` is `knocks.json`'s `current`, used only when it names this record by sha.

**The night's to test** (`whose() == "night"`) only when all of these hold:
1. `kind` is `"dropped"` or `"unavailable"`;
2. `machine == "github"`;
3. `ref == "refs/heads/main"`;
4. `dry is False`;
5. `retry_after` is absent or at most 160 h;
6. `k` has no `person`, fewer than 4 knocks, and its `since` is under 384 h (16 days) ago;
7. `refusal.knock_on()`: `NIGHT_KNOCK` is exactly `on` **and** `NIGHT_PERSON_CHECK` is exactly `set` (§2.11).

**Both doors read it.** The knock (§2.3 step 2, and `check(knock=True)` in the child) and the database (`from_database(held=True)`) are open only when `whose() == "night"`. There is no second function. A record that becomes a person's, for any reason, closes both. That includes a block-type answer to a knock, the fourth unanswered knock, 16 days, or the switch turned off.

**Anything else is a person's.** That covers:
- every record with no kind, of any age, the standing 29 October record and every preflight fixture included (`preflight.py` 81660, 82539, 89555, 89589, 90013);
- `"refused"`;
- laptop-written records;
- dry-run-written records, and any record not written by `refs/heads/main`. Main's night trusts only a kind that main's code wrote;
- a `retry_after` over 160 h;
- any record while the switch is off or the third check is not set.

**Rule A: the drop night ends as today.** The night that meets the drops takes nothing from the database. It ends, and the workflow sends the record to R2 within seconds (`nightly.yml:449-459`).
- The database is used only from the next run that finds the record on file.
- Why: the record must reach the bucket before any database night or build (safety judge). The project already decided this for a refusal met by the night's documents (`feat/night-documents` `nightly.py:873-885`, `BUILD_REFUSED`: "a refusal met tonight ... ends the night before its build: the refusal reaches the bucket moments after the asking"). The workflow's own comment says "the laptop has to know at once" (`nightly.yml:447-448`).
- The cost is one stale day per outage, whatever its length (§13 says what the same-day version would take).

**After 16 days.** A person who wants database nights back while the website is still out clears the record by hand. The next night asks the website as any night does (two requests at most if it is still dropping). A new drop then starts a new chain: a new `since`, no knocks, a new day-0 email. A person's clear never writes `lifted`, so nothing is carried.

### 2.3 The night's order (`nightly.py`, the fetch block, nc `1616-1735`)

1. `gc_quiet()`, unchanged in meaning: may the website be asked tonight? Any record, or a held lock, says no.
   - Its sentence still begins "a refusal is on file" (`_nightly_runner` reads that).
   - It then names whose the record is and, for the night's, when the next knock is due.
2. **The knock**, `knock(a, night)`, only when all of these hold:
   - `--runner`; not `--dry-run`; not `--new-term`; not `not_main()` / `dry_by_workflow()` (nc `2142`, `2166`);
   - no lock is held;
   - `whose() == "night"` (which includes the switch and the third check);
   - `knock_due()`;
   - `asking_left(KNOCK_MINUTES + EXPORT_MINUTES)` = `asking_left(42)` returns a deadline.

   On a lift, `gc_quiet()` is read again and the night is an ordinary night, **with one difference: the export gets one try.** The loop breaks after try 1 whatever came back. Setting `last = 1` is not enough, because nc `1689` resets `last` after the database. The check is a `lifted_tonight` test beside `if tries >= last` (nc `1690`). An empty export on the lift night still goes to the database on try 1 (`DB_AFTER_TRIES = 1`, nc `2686`), as any night. What it never does is wait 30 minutes (`EMPTY_WAIT`, nc `2639`) and ask the export again.
3. **Not lifted, and `whose() == "night"`** (and `--runner`, not `--new-term`, no lock held): the held path, under `refusal.hold("nightly")`:
   - `v["fetch"] = "held: ..."`; no export try;
   - `from_database(a, night, 0, asked, held=True, because=...)` once;
   - then, if it installed, the study views, term data and statutes (database);
   - the bill requests and the lists (website) are "not asked for: held", keeping the copies on file;
   - then the build, `check_site` and the gate, as any database night.
4. **A person's record:** "FETCH DEFERRED", exactly as today (nc `1629-1632`). No database.
5. **No record:** today's loop, unchanged. That includes the drop night, rule A: the break at nc `1662-1664` still stops before `from_database` on a refusal.

`from_database()` refuses (nc `3086-3090`) unless `held=True` and `whose() == "night"`. Its other refusals are unchanged:
- a New term run;
- no installed files;
- `probe_db`'s own hold;
- `judge()`'s stops, `DB_LOOKED_WRONG`, `DB_STOPPED_MOST`, the shrink rule.

**A night that never asks the export: the answers the code already asks for.** dev `nightly.py:2600-2610` says that "THE EXPORT IS STILL ASKED FIRST, every night", and that a night which never asked it "would need an answer to each" of six things. It calls that "a person's decision, and a piece of work of its own". D3 is that decision. Each of the six is answered here. Each is bounded by 16 days, because the database closes when the record becomes a person's (§2.2):

| What only the website gives (dev 2603-2609) | On a held night |
|---|---|
| `Members.txt` | The installed copy stays (`from_database`, dev `3083-3106`, "the installed one: tonight's did not arrive"). Its note says "not asked: the website is held" |
| The six lookups | `fetch_day_db` reads five to compare and installs none (`fetch_day_db.py:38-39`). The installed lookups stay |
| The page's own "Error Generating" | Not asked, so nothing is said. The verdict's `data_page_said` is absent and `v["fetch"]` says "held" |
| The archive's history of the website's files | A held day adds no snapshot day. The run's page says so; the gap is the length of the hold |
| A new session year or a new term | A newer year in the views is "seen, left out, and said (a warning, not a stop)" (`src/parse/dayfiles_from_db.py:374-377`). So a hold across the start of a session year leaves the new year's rows out until the export returns. That is a real gap, at most 16 days, said on the page. A new term never comes from the database (`from_database`'s first refusal; dev `3006-3010`), and needs a person anyway (read_holds rank 2) |
| The guards comparing the database with its own files | The `DB_NIGHTS_MOST` alarm at 7 nights (nc `1133`, `5537-5545`), which emails (§2.9). Then the database closes at 4 failed knocks or 16 days |

The bill requests and the calendar and journal lists (nc `1701`, `1717`, `1729`) are asked on today's empty-export database nights, but not on held nights. That is one more reason the 16 days must end the database too, not only the knocks.

### 2.4 The knock, exactly

| | |
|---|---|
| **Request** | One `GET https://gc.nh.gov/dynamicdatadump/Counties.txt` (`BASE`, `snapshot_gencourt.py:104`; in `FILES`, `:119`). 195 bytes on 28 October (that night's log, line 1697). On the path that dropped. |
| **Headers** | The snapshot's own `UA`, `granite-record/1.0 (civic transparency archive; contact@graniterecord.org)` (`:124-125`) |
| **Limits** | 60 s socket timeout (`KNOCK_TIMEOUT`). An opener built **without** `HTTPRedirectHandler`, so a 3xx comes back as an answer and no second request is made. No retry. The child is killed at `min(120 s, seconds_left(deadline))` (`run(timeout=)`, `RUN_KILLED` 124, nc `1192`, `1239`). |
| **Never** | the data page `dynamicdatadump/` (it "rebuilds every table before it answers", `:217-232`); `Members.txt` (82,694 bytes, another path); an invented path; another host; `bill_status/legacy/bs2016/`; netcheck |
| **From** | GitHub's runner, as the child `snapshot_gencourt.py --knock`, started by `nightly.knock()` inside `refusal.hold("nightly")` and the `gc-night` job group (`nightly.yml:246-248`; `weekly.yml:102`) |
| **The gate, in the child** | `main()`'s `--knock` branch calls `refusal.check("The knock", knock=True)` **first**, then `with refusal.hold("the knock")`. `check(knock=True)` exits 2 and asks nothing unless all of these hold: `GITHUB_ACTIONS == "true"`; not dry; ref main; `MARK` exists and reads; `whose() == "night"`; `knock_due()`; `refusal.night_window()` is the daily window; **and the UTC time is before `KNOCK_LATEST` (11:18)**. It reads `MARK` at any age, not through `standing()`. Only this one call may pass `knock=True` (C5's AST case). |
| **Write first** | `refusal.knocking(url)` appends `{"answer": "no answer", ...}` to `knocks.json` (part file, then rename) **before** the request. `refusal.knocked(answer, said, retry_after)` then rewrites it. A killed knock still counts. |

**What the answer decides.** The knock asks whether the server answers. It does not ask whether the General Court's export is built. Asked alone, without the page that rebuilds the files, a file returns "whatever the last visitor's rebuild had left" (`snapshot_gencourt.py:217-230`). In October, `Counties.txt` came back "not a data file (0 bytes)" or "(3 bytes)" over a 200, even after the page, on 7 of the 29 main nights from 30 September to 28 October: 1, 2, 3, 4, 5, 9 and 12 October (the bucket's night logs). The night never reads an empty export as a refusal: it goes to the database (nc `1662-1671`). So neither does the knock.

| Answer | Result | Exit |
|---|---|---|
| 200, no block page (`refusal.classify(body=…)`, as `read_one`, `:342`), not HTML (`read_one`'s test, `:346-347`), **any size, 0 bytes included** | **lifted** (§2.6). If the files then come back empty, the lift night's export takes the database path it takes on any night | 0 |
| 403; 429; the block page at any status; any 3xx; a 503 whose body has the block page; a `Retry-After` on anything but a 503; a 503 `Retry-After` over 160 h | **a person's for good** (`person` set): the knock and the database close | 2 |
| dropped, reset, refused or timed out; a bare 503 (next due no sooner than its `Retry-After`); 404 or 410; another 5xx; a 200 that is a web page (HTML: a maintenance page is an outage); killed | **a failed knock**: the next rung, or a person's if it was the fourth | 1 |

**"Stable" means one answer, and then the night's own export.**
- After a lift, the snapshot asks its usual page and 14 files.
- For a week after a lift, the first drop ends that export (§2.7).
- A relapse keeps the ladder (§2.7).
- Two knocks minutes apart would double the requests to a server that may be blocking. They would also prove less than the export does.

### 2.5 When: the ladder, the clock, the caps

| Constant | Value | Why |
|---|---|---|
| `KNOCK_HOURS` | `(16, 40, 88, 160)` | Counted from the last failed request: the refusal, a relapse, or the last failed knock. That is a day, two, four and seven, each 8 h short so the next morning finds it due. |
| first rung 16, not 24 | | The 29 Oct record is at 08:27:15. The next timer night asks at about 08:23-08:27, which is 23.9-24.0 h later (08:17 start, kit-down, about 6 min of preflight; read_night §2). |
| first rung 16, not 20 | | GitHub's cron ran nights as late as 15:38 UTC on 19-24 Oct (read_holds rank 12). 15:38 + 16 h = 07:38, still due by the next 08:17. |
| `KNOCKS_MOST` | 4 | After the fourth unanswered knock the record is a person's |
| `HELD_MOST_HOURS` | 384 (16 days), from `since` | A record the clock never lets the night test (the timer's token lapsed, every night late) still becomes a person's. 12.7 days of rungs plus mornings, plus two days' slack. Both doors close then (§2.2) |
| `RELAPSE_HOURS` | 168 | A record noted within a week of a lift carries the lifted record's knocks and `since`. For the same week the export stops at its first drop |
| `RETRY_AFTER_MOST` | 160 h | Longer is "go away for a week": a person's |
| `KNOCK_MINUTES` | 2 | the child's kill |
| `EXPORT_MINUTES` | 40 | Computed: the page's 300 s (`PAGE_TIMEOUT`, `:232`) + 15 requests × 120 s (`get()`, `:277`; 14 files and one retry) + 15 pauses × 5 s (`--delay` 4.0 × 1.25, `:500`, `:592`) + the 60 s retry wait (`:629`) = 2,235 s = 37.25 min, rounded up. Design_minimal's 36 left out the retried file's own request (safety judge). The week's one-drop rule only shortens this |
| `KNOCK_LATEST` | 11:18 UTC, in `refusal.py` | `ASK_UNTIL` (nc `721`, 12:00) less `KNOCK_MINUTES + EXPORT_MINUTES`. It is the child's own copy of the parent's `asking_left(42)`, so that removing the parent's gate in a refactor still leaves no knock after 11:18. C13 pins the two together |

**The clock (nc `asking_left`, `3923-3962`).** The knock starts only inside the daily window (08:00-13:30 UTC, `refusal.py:522`) **and** only if `now + 42 min` falls before `ASK_UNTIL` 12:00 UTC. The child checks the same 11:18 itself. So the knock and the whole export it may open fit before 12:00 *on the export's computed worst case*.
- **Said plainly:** a socket timeout bounds one read, not a request (nc docstring), and the export after a lift keeps "its own rule" (nc `447-468`): it is not killed. A server that trickles bytes could keep it past 12:00, as it could on any night today. The laptop's window runs to 13:30.
- The lift night's single export try (§2.3) means no second try starts 30 minutes later, past 12:00.
- A night GitHub starts after 11:18 gets "not asked for: it is HH:MM UTC" for the knock (a `clock_kind` warning, never holding the gate). It takes the database, and the next on-time night knocks.

**The ceiling the numbers give:**
- **At most one knock per UTC day.** Knocks happen only 08:00-11:18 UTC. The shortest rung (16 h) is longer than that window. `knock()` runs at most once a run. `gc-night` serialises the night and weekly jobs, so a later run reads what the earlier one sent.
- **At most four knocks per outage**, counted across relapses within 168 h. C2b pins the carry that makes this hold.
- **No knock and no database after 16 days** without a lift.

### 2.6 The lift, the bucket and the laptop

**`archive/knocks.json`** (R2 `state/knocks.json`), written only by `refusal.py`:

```json
{
 "current": {"refusal": "<sha256 of refused.json's bytes>", "since": 1793262435.0,
             "knocks": [{"utc": "2026-10-30T08:23:40Z", "epoch": 0, "run_id": "…",
                         "url": "https://gc.nh.gov/dynamicdatadump/Counties.txt",
                         "answer": "dropped", "said": "closed without a byte", "retry_after": null}],
             "person": null, "carried_from": null},
 "lifted": [{"refusal": "<sha>", "utc": "…", "run_id": "…", "said": "Counties.txt, 195 bytes",
             "text": "<refused.json's exact text>", "knocks": ["…"]}]
}
```

- `note()` on GitHub starts `current` for a record that is the night's to test. On a relapse it carries the knocks and `since` (§2.7).
- **`lifted` is never pruned.** Each entry is about 1 KB, one per lift. It must outlive any copy a laptop could still hold, so that `pull` and `send_refusal` recognise a lifted record at any age (below).

**The lift, on the runner.** `knocked("whole", ...)`:
1. appends to `lifted` the record's **exact text**, with `refusal` = the sha of the bytes read **before** the knock. Those are the bytes `state-down` brought down, so they match the bucket's;
2. writes `knocks.json`;
3. only then removes `archive/refused.json`.

The record is moved into `knocks.json`, not lost. This follows `_cloud_state_and_site`'s "moved, never deleted" (`preflight.py:55341-55344`).

**The lift, in the bucket.** `cloud.lift_refusal()` runs first in `state_up()` (`cloud.py:1627`).
- **It acts only when all of these hold:**
  - `only is None` (not a dry night);
  - `GITHUB_ACTIONS == "true"`;
  - `GITHUB_REF == "refs/heads/main"` exactly;
  - `DRY_RUN != "true"`;
  - the bucket's `state/refused.json` has the sha this machine's `state-down` took down;
  - that sha is in local `knocks.json["lifted"]`.
- **What it does:** it moves the object to `replaced/<day>/` (`Replacer.keep`, then `delete`, as `clear-refusal` does, `cloud.py:2103-2105`) and records it as `cleared` in this machine's state record, so no later `state_up` sends it back.
- **Otherwise it moves nothing** and says why. That is the safe direction: the next night finds the record and knocks again when due.
- **No new workflow step is needed.** The final "Send the state files back to R2" runs `always()` (`nightly.yml:534-543`). On a relapse night "A refusal goes to R2 at once" runs it first: the old record moves, then the new one goes up through `state_up`'s `old is None` path.

**The laptop reads the lift from the bucket, not from a local "cleared"** (the trap at `cloud.py:2108-2112`, `2801-2813`):
- **`pull_refusal`** reads `state/knocks.json`. A laptop copy whose sha is in `lifted` gets a line, **at any age**, never the "IS NOT IN THE BUCKET" failure and never the "send-refusal sends it" advice. The line reads: "THE NIGHT LIFTED THIS REFUSAL on <date> after one request was answered. It is still on file here: the lane and every fetch here stop at it until python3 refusal.py --clear". The unsent marker is lifted for it.
- **`send_refusal`** never sends a sha in the bucket's `lifted`.
- **The laptop's copy stays.** It is never set aside by a pull. The lane (`gc_lane.py:402-406`) and hand fetches (§2.10) stop at it until a person runs `refusal.py --clear` there. This is design_fresh's D6 reversed, as the safety judge asked.
- **Who sees it.** On the stood-down laptop the lane cannot ask anything after a night window until a person has run `pull` (`refusal.gc_turn`, `refusal.py:730-744`; `gc_lane.py:46-54`). That pull prints the line above. The day-0 email and the lift's line on the run page also name the laptop's clear (§2.9). The existing "laptop's share" warning (`laptop_share_behind`, nc `3755`) is the backstop after `STILL_DAYS` (nc `3480`).

**Dry runs never lift:**
- `knock()` is never called on a dry run;
- `check(knock=True)` refuses one;
- `note()` marks a dry run's record `dry`, so it is a person's;
- `knocks.json` joins `DRY_NEVER` (`cloud.py:457`) and stays out of `dry_run.state` (`cloud_kit.json:226`);
- `lift_refusal` never runs with `only`.

### 2.7 Relapse, flapping, and the bounds

- **Relapse.** `note()` on GitHub, for a record the night tests, looks at `knocks.json["lifted"][-1]`. If that lift was under 168 h ago, the new `current` starts with its knocks (the answered one included), its `since`, and `carried_from`. So the next wait is the next rung, the fourth knock in the chain ends it, and the 16 days still count from the first drop. C2b pins this.
- **The week after a lift: one drop ends the export.** New `refusal.drops_allowed()` returns 1 while `lifted[-1]` is under `RELAPSE_HOURS` old, and 2 otherwise. The snapshot's drop count (`snapshot_gencourt.py:612-621`) and `fetch_committees`' (`:233-234`) compare with it. At 1, the page's drop ends the run, as a file's does, and there is no 60 s retry (`:626-630`).
  - Why: a blocked address drops from the first request. Run 151's page and first file both dropped (log 1657-1658), and so did netcheck's account of an earlier episode (`netcheck.py:13-17`). In the week after a lift, a drop is evidence, not bad luck.
  - The cost, measured: in the 30 main night logs from 30 September to 29 October, the retry ("once more in a minute") never ran, and the only drops were run 151's two.
- **A relapse on the lift night** (knock answered, export dropped) ends as a drop night: rule A, nothing built. It costs the knock plus the export up to its first unanswered request: 2 when the page drops, and at most 16 (the knock, the page, 14 files) with exactly one unanswered.
- **A person's record is never carried.**

### 2.8 503, decided

- **`classify()` is unchanged**, so a 503 still ends a run at once, and `_every_fetcher_notes_refusal`'s 503 cases (preflight 77970-77974) stay green.
- **The new `refusal.unavailable(err)`** returns `None` unless the error is an `HTTPError` with code 503 whose first 4,000 body bytes do not match `BLOCKED`. Otherwise it returns `Retry-After` in seconds (0 if absent; seconds or an HTTP date).
  - This is needed because `classify()` returns before reading a 503's body (`refusal.py:286-287`).
  - The snapshot's `read_one()` and `open_page()` use it to name the kind `"unavailable"`.
- **Resumable, on the ladder.** It is never knocked before `max(rung, Retry-After)`. A `Retry-After` over 160 h is a person's. It is never capped or shortened (a fix to design_fresh's 168 h cap).
- **429 stays a person's.** It is a complaint aimed at our rate.
- **A `Retry-After` on any other status stays a person's.**

**Why 503 is resumable.**
- A 503 is the server's own "not now". *Guess:* IIS answers it while an application pool is stopped or recycling, which is the maintenance outage the owner asked about.
- The firewall's known faces are the block page and drops (`refusal.py:265`; netcheck's account at `:13-19`), never a bare 503.
- It adds no new kind of risk: a 503 that is really a block gets the same at most four single requests as a drop that is really a block.
- No 503 from gc.nh.gov is recorded anywhere (read_history §3B).
- **This is the owner's decision (D4).**

### 2.9 What the person hears

**Healthchecks emails only when a check changes state** (dev `nightly.py:5683-5690`: "a refusal held for three nights is one email"; nc `nightly.yml:568-618`). The night's check cannot carry "this is now yours": by that moment it is often already down. It went down on day 0. It goes down again on the 7th database night, because an alarm makes the night not clean (nc `5541`, `5583`, `5935`). So that message gets a check of its own.

**The third check, `HEALTHCHECKS_PERSON_URL` ("a refusal is yours").**
- `--close` writes `logs/alert-person.txt` every night (`ALERT_PERSON_FILE`, from new `person_alerts_of(v)`). It holds the record's line when a refusal on file is a person's, and nothing otherwise, including while the night tests one.
- The existing step "Tell Healthchecks how the night ended" (nc `nightly.yml:568`) gains `HC_PERSON_URL` and three cases:
  - a non-empty file: `/fail` with the file as the body;
  - an empty file: a plain ping;
  - no file (`--close` never ran): no ping, and the night's own check says why.
- It is a dry run's never (the step's existing `-cne refs/heads/main` test, nc `nightly.yml:577`).
- Because the check is pinged "up" on every night without a person's record, its **first `/fail` is always a change, so always an email.** That holds whatever the night's check is doing.
- The method is off without it (§2.11). So whenever the night tests a record, this email is guaranteed to be possible.

| Moment | Night's check (`HEALTHCHECKS_URL`) | Third check (`HEALTHCHECKS_PERSON_URL`) | Warnings' check (`HEALTHCHECKS_WARN_URL`) | The run's page and verdict |
|---|---|---|---|---|
| Day 0: the drops, a record the night tests | `/fail` (not clean): **email**. The body says what happened, gives the knock dates, says "nothing is needed from you on GitHub's side; if the night cannot settle it, the 'refusal is yours' check will email you", and says the laptop's next pull will ask for `python3 refusal.py --clear` there | ping (up) | — | the record, `web.next` |
| Day 0: a block-type answer, or any record that is a person's from the start (laptop, dry, kindless, switch off, no third check) | `/fail`: **email**, naming `clear-refusal` (today's line) | `/fail`: **email** (if set) | — | the reason |
| A held database night (clean) | success: **"up" email** the first time | ping | the held line | "held: …", the knock's line |
| A failed knock, 1 to 3 | success | ping | the held line, with "knock N of 4 was not answered; next on …" | the same |
| The 7th database night in a row | `/fail`: **email** from the `DB_NIGHTS_MOST` alarm, its sentence generalised to the cause ("the website has not been asked since <date>; the next knock is on <date>; the record becomes yours by <date> at the latest") | ping | — | the alarm |
| The lift | success | ping | — | `v["knock"] = "lifted: …"`, and a line naming the laptop's clear |
| **It becomes a person's** (a block-type answer to a knock, the fourth failed knock, 16 days, the switch turned off) | `/fail` (often already down: no email) | **`/fail`: email, always**. The body says which, and for a block-type answer says the IT office or the Clerk's office may need a message | — | the reason |
| A person clears it | success on the next good night | ping: **"up" email** | — | — |

- `alerts_of()` carries the record's line **only** when it is a person's or the night was not clean (unchanged).
- `warns_of()` carries it while the night tests it.
- `person_alerts_of()` carries it exactly while it is a person's.
- **The warnings' check is likely already down.** If `HEALTHCHECKS_WARN_URL` is set, 29 October's verdict sent it `/fail` for the captions inbox (`warn_alerts`: "Nothing has arrived in the captions inbox since 2026-10-25"), so the middle lines may send no email. That is why nothing that needs the person goes only there.
- **Backstop.** The publish check (`HEALTHCHECKS_PUBLISH_URL`, pinged only by a landed publish, `nightly.yml:745-757`) goes down once nothing has published for its period, and emails. *Guess:* about two days, from the comment at `nightly.yml:760-761`.
- **The lift adds no warning kind.** A new kind would hold the night for approval (`warning_reasons`, nc `4978`).

### 2.10 The weekly, a New term run, dry runs, the laptop

- **The weekly** (Monday 04:17 UTC, `weekly.yml:51`; nc `nightly.py:6141`):
  - It never knocks.
  - Under a record the night tests, its database pieces run, and `fetch_committees` is "not asked for: held", which does not count as `bad`.
  - A person's record defers everything, as today.
  - A Monday weekly's drops (`fetch_committees` now passes a kind, and reads `drops_allowed()`) are tested by Tuesday's night. 04:20 + 16 h = 20:20, so Monday's night 4 h later finds it not due and takes the database.
  - The weekly pings no check on success (`weekly.yml:214-237`, only `/fail` on failure). The third check is the night's to ping, and the next night does.
- **A New term run** never knocks and never uses the database (`from_database`'s first refusal). Under any record it stops before asking and says how to clear it. A person is running it anyway (read_holds rank 2).
- **Dry runs** never knock or lift. Under a main-written record the night tests, a dry run may take the database, as dry runs do today on an empty export.
- **The laptop: one tightening.** `check()` (hand fetches) stops at a record with `machine == "github"` and any `kind` **at any age**, not just `QUIET_HOURS`. It says so: "GitHub's night met this; it tests it itself; nothing here asks until python3 refusal.py --clear".
  - This closes the gap the safety judge found: today a hand fetch passes silently once the pulled record is over 24 h old (`refusal.py:211-232`), even while the night is held.
  - Kindless and laptop-written records keep their 24 h, so existing checks stay green.
  - Database fetchers never call `check()` (`fetch_day_db.py:63-66`, `fetch_past_db.py:89`), so nothing on GitHub changes.
  - On the laptop, `knock_on()` is false (neither variable is set there), so `whose()` says "a person's" for every copy the laptop holds. That is true of the laptop's copy, which only a person clears.

### 2.11 The off switch, and the third check as a condition

- Two lines in the workflow-level `env` of `nightly.yml` (beside `DRY_RUN`, nc `147-160`) and of `weekly.yml`, the way `NIGHT_DOCUMENTS` is read on `feat/night-documents` (its `nightly.yml:196`):
  - `NIGHT_KNOCK: ${{ vars.NIGHT_KNOCK || 'on' }}`
  - `NIGHT_PERSON_CHECK: ${{ secrets.HEALTHCHECKS_PERSON_URL != '' && 'set' || 'none' }}`. Only whether the secret is set reaches the night, never its URL. *Guess, to be confirmed by the first dry run's log:* that GitHub evaluates `secrets` in a workflow-level `env` expression as written.
- `refusal.knock_on()` is true only for exactly `on` and exactly `set`. It lives in `refusal.py`, and **`whose()` reads it** (§2.2, condition 7). So with the switch off, or the third check missing, every record is a person's: for the gates, for the alert's wording (`clear-refusal`, no knock date) and for its routing. That is today's behaviour exactly, plus the third check's email if it is set.
- The owner can set `NIGHT_KNOCK` in GitHub's settings without a commit. An unexpected value reads as off. That is the safe direction, and the opposite choice from `NIGHT_DOCUMENTS`, which defaults to off anyway.
- A record the night was testing when the switch goes off becomes a person's on the next night. The third check then emails. Turning it back on resumes the same chain if it is still under 16 days and 4 knocks.

---

## 3. The request ceiling, in every failure mode

**The ordinary night's web requests:**
- the page;
- 14 files and at most one 60 s retry;
- up to 3 bill requests;
- 4 to 8 listing requests.

That is at most about 28. Below, "web" is gc.nh.gov and "SQL" is PublicSQL.

A database night is 11 connections for the day files (`fetch_day_db.py:30`, `PAUSE` 4 s, `:96`), plus 2 study views (`STUDY_NIGHTLY`, nc `678`), 3 term views (`TERM_VIEWS`, nc `1089`), and the statutes on 6 nights a year (`STATUTE_NIGHTS`). That is the same load as each of the five October database nights, all installed. Any failed connection stops it through `probe_db`'s own hold (20/44/92/164 h, then one connection a night).

| Failure mode | Web: today | Web: this method | SQL: this method | Stale days |
|---|---|---|---|---|
| **Outage under a day** (29 Oct, if it was one) | 2, then 0 until a person; then netcheck's 8 | 2 on day 0; 1 knock on day 1, which lifts; then ordinary nights | none | 1 |
| **Three-day outage** | as above | 2; knock day 1 fails; knock day 3 lifts. **4 in all** | database nights on days 1 and 2 | 1 |
| **Two weeks or more, every knock unanswered** | as above | 2 + knocks on days 1, 3, 7 and 14 = **6 single requests in 14 days**, then 0 | database nights on days 1-13 (the 7th emails); **closed from day 14** | 1 until day 14; then until a person (third check emails) |
| **A block on one GitHub address that shows as drops, other addresses answering** (*guess* that runner addresses vary, §10 risk 2) | as above | **At the blocked address, at most 6 per chain**: 2 on day 0, then 1 a night. That 1 is either a failed knock or the first drop of a relapse night under the week's one-drop rule. A knock that lifts came from another address, and its export goes from there. ≤ 4 knocks, ≤ 16 days. Nights on other addresses are ordinary nights | database nights between | relapse nights |
| **Clock never allows a knock** (timer down, every night after 11:18) | as above | 2, then 0 | database nights to day 16 (14 Nov on 29 Oct's dates), then closed | 1; then until a person |
| **Block page, 403 or 429 on the night** | 1, then 0 | 1, then 0 from both machines | **0** | until a person |
| **Block page, 403, 429, 3xx, or 503 with the block page, answered to a knock** | — | that knock, then 0 | **0** from then | until a person |
| **Bare 503, no `Retry-After`** | 1, then a person | 1, then at most 4 knocks over 14 days, as for drops | database nights, to 16 days | 1 |
| **503 with `Retry-After` R ≤ 160 h** | 1, then a person | 1, then no knock before R, at most 4 | database nights, to 16 days | 1 |
| **503 with R > 160 h** | 1, then a person | 1, then 0 | 0 | until a person |
| **Flapping**: the knock is answered, the export drops | — | per lift night, the knock + the export up to its **first** unanswered request, no retry: 2 when the page drops, at most 16 with one unanswered. At most 4 such nights per chain (carried ladder) | none on relapse nights (rule A); database on the nights between | a relapse night is stale |
| **The runner dies after a failed knock, before exit** | — | `knocks.json` never reached the bucket, so the next night may knock one rung early. Still at most 1 a day; `since` and the 16 days come from day 0's upload | — | — |
| **The switch off, or no third check** | as today | as today: 2, then 0 until a person | 0 | until a person |
| **Dry runs, under any record** | 0 | 0 (never knock) | database while the night tests the record | — |
| **The laptop** | its own, as today | no change in what it asks. Hand fetches now stop at a GitHub record at any age | none | — |
| **The weekly under a record** | 0 | 0 | its four database pieces while the night tests the record | — |

**Why the blocked-address row is 6 and not 4 × 17.** Each of a chain's at most four knocks either fails at the blocked address (1 request) or lifts from another one. A lift is followed by at most one relapse before the next knock is due, because the relapse writes a record. A relapse night at the blocked address stops at its first request (the page) under the week's one-drop rule. So the blocked address sees 2 on day 0 and then at most one request on each of at most four nights. A relapse more than 168 h after a lift is a new outage: 2 requests, a new chain, and a new day-0 email.

**Comparisons:**
- The first block was about 1,000 requests for guessed filenames (`probe_calendars.py:13-18`).
- netcheck is 8 requests over two hosts, 7 of them with a browser User-Agent (read_refusal).

**No request ever comes from:**
- the laptop because of this method;
- a cloud container;
- the live Worker or anything on Cloudflare.

**No knock ever:**
- happens outside 08:00-11:18 UTC;
- is the data page;
- follows a redirect;
- is retried.

---

## 4. What stays a person's decision, and why

| Stays a person's | Why |
|---|---|
| A 403, a 429, the block page at any status, a `Retry-After` on anything but a 503, met on the night | These are the address being told no. Both recorded blocks cost "days and an email to a Clerk's office" (CLAUDE.md:58). Contact during one is the risk the rule exists for. |
| The same answered to a knock, and any 3xx to a knock | A redirect from a data file's address is not a data file. Following it would be a second request to an unknown target. |
| The database during any record that is a person's (part of D3) | A true block is the case that ends in a letter to the Clerk's office. The person should be able to say nothing of ours has asked since. After 16 days, the website-only pieces are too old to publish under "The record as of <today>" (`src/pages/print.js:1155-1157` dates the record from `build.json`'s finish) |
| A fourth unanswered knock; 16 days without a lift | Two weeks of drops is no longer a passing outage. The web-only pieces (`Members.txt`, the lookups, bill requests, lists, committee rooms) have aged that long, and the database has been compared with itself (dev `2607-2609`). Both doors close, and the third check emails |
| Every refusal met on the laptop, and the laptop's copy and lane | The laptop is the address blocked twice, and it is attended. Its share of the record is already a person's to start (read_holds rank 8). |
| Every refusal met by a dry run, or written by code not on `main` | Main's night must not act on a kind unmerged code wrote |
| Every record without a kind, **the standing 29 Oct record included** | Nothing before this change can tell a drop from a 403 (`refusal.py:113-127`) |
| Every record while the switch is off or the third check is missing | The method never resumes on its own without a way to say when it has stopped |
| Clearing any record sooner: netcheck, then `cloud.py clear-refusal` and `refusal.py --clear` | Unchanged. A person's clear always wins: the bucket's record moves, and a `knocks.json` `current` about it is then ignored. |
| Writing to the General Court's IT office | |
| Turning the method off (`NIGHT_KNOCK`) | |
| The approval gate, the new term (2 Dec), expired credentials | Unchanged. A lift restores fetching, not necessarily publishing: the release proof lapses after 48 h, more than 600 rows changed, a new warning kind (read_holds §3.2). |
| CLAUDE.md, and the assistant guard's rows | These are configuration and the owner's file |

---

## 5. Code changes, by file and function

**`refusal.py`** (`2026-09-09.19` becomes `.20`)
- **Constants:** `RESUMABLE = ("dropped", "unavailable")`, `KNOCK_HOURS`, `KNOCKS_MOST`, `HELD_MOST_HOURS`, `RELAPSE_HOURS`, `RETRY_AFTER_MOST`, `KNOCK_LATEST = (11, 18)`, `KNOCKS = Path("archive/knocks.json")`, `MAIN_REF = "refs/heads/main"`.
- **`note(where, why, kind=None, retry_after=None)`** (`:113-127`):
  - writes the §2.1 fields;
  - on GitHub, for a record the night tests, writes `knocks.json["current"]`, with the relapse carry (§2.7);
  - `tell_the_bucket` is unchanged.
- **`unavailable(err)`** (§2.8).
- **`knock_on()`**: `NIGHT_KNOCK == "on"` and `NIGHT_PERSON_CHECK == "set"`, both exact.
- **The readers:**
  - `whose(d=None, k=None, now=None)` returns `("night" | "person", why)`. It reads `knock_on()`. It is the only gate for the knock and the database;
  - `knock_due(d, k, now=None)` returns `(bool, due_epoch)`;
  - `knock_schedule(d, k)` gives the dates a knock may come, if each fails;
  - `drops_allowed(now=None)`: 1 within `RELAPSE_HOURS` of `lifted[-1]`, else 2.
- **The writers:** `knocking(url)`, `knocked(answer, said, retry_after=None)`, the lift (§2.6). Each writes a part file, then renames. `lifted` is never pruned.
- **`check(who="", knock=False)`** (`:223-252`):
  - with `knock=True`, the gate in §2.4, `KNOCK_LATEST` included;
  - without it, a GitHub record with a kind stops at any age (§2.10). Otherwise unchanged.
- **`force()`** (`:195-208`), and **`main()`'s status** (`:855-867`, which says an old record "no longer stops anything": false for the night and the lane today): say whose the record is and when the next knock is due. Off GitHub, where `knock_on()` is false, a GitHub record with a kind is described as "GitHub's night decides whether it tests this itself; its run page says", not as plainly a person's, so `pull`'s wording does not contradict the night's.
- **Docstring:**
  - "HOW IT BEHAVES" (`:30-38`) gets "THE NIGHT'S KNOCK (<date>, the person's decision)";
  - "Nothing clears it automatically" becomes "Nothing clears a person's refusal automatically. One kind is the night's to test, with one request a day at most: THE NIGHT'S KNOCK."

**`src/fetch/gc_web/snapshot_gencourt.py`** (`2026-09-04.13` becomes `.14`)
- **Constants:** `KNOCK_NAME = "Counties.txt"`, `KNOCK_TIMEOUT = 60`, and `_no_redirect_opener()`.
- **`read_one()` and `open_page()`** return the kind `"unavailable"` and the `Retry-After` for a 503 that `refusal.unavailable()` accepts.
- **`run()`:**
  - stops at once on `"unavailable"` as on `"refused"`;
  - passes `kind=` and `retry_after=` at `:585`, `:615` and `:621`;
  - the drop count compares with `refusal.drops_allowed()` instead of 2 (`:587-588`, `:618-630`). At 1 there is no retry. At 2 it is unchanged.
- **`main()`:** a `--knock` branch after `--plan` and `stand_down()`. It calls `refusal.check("The knock", knock=True)`, then `with refusal.hold("the knock") as held: return knock(held)`. The normal path's `refusal.check("The daily snapshot")` (`:517`) is unchanged.
- **`knock(held)`:** `held.still()`, `knocking()`, one request through the no-redirect opener, the judgement in §2.4 (any size), `knocked()`. It returns 0, 1 or 2.
- **`:683`:** "refusal.py holds every fetch for a day" becomes "refusal.py holds every fetch until a person clears it, or, for one the night tests itself, until its one request is answered (refusal.py, THE NIGHT'S KNOCK)".

**`src/fetch/gc_web/fetch_committees.py`:** `kind=` at `:235` (from `classify`/`unavailable`) and `"refused"` at `:241`; `dropped >= refusal.drops_allowed()` at `:234`.

**`nightly.py`** (on nc's stamp)
- **Constants:** `KNOCK_MINUTES = 2`, `EXPORT_MINUTES = 40`, `WEB_HELD_SAID`, `KIND_WEB_HELD` (added to `KINDS_FALLBACK`, nc `995`), `ALERT_PERSON_FILE = Path("logs/alert-person.txt")`.
- **`knock(a, night)`**, the one place the night knocks: §2.3 step 2. It sets `v["knock"]` and `v["web"]` (`{state, kind, since, knocks, next, lifted}`). It turns `RUN_KILLED` into a failed knock (the child already wrote "no answer").
- **The fetch block** (nc `1616-1735`): §2.3.
  - The held path calls `from_database(..., held=True, because=WEB_HELD_SAID ...)`.
  - The study views, term data and statutes read `db_open = not MARK.exists() or held`.
  - The bill requests and lists read `not MARK.exists()`, as today. Otherwise they are "not asked for: " + `WEB_HELD_SAID`.
  - On a lift night the export loop ends after try 1 (§2.3 step 2).
- **`from_database(a, night, tries, since, held=False, because=None)`:** the gate (nc `3086-3090`) reads `held and refusal.whose()[0] == "night"`. `because` goes to `day_files.because` and its `tried` line.
- **`gc_quiet()`** (nc `1308-1321`): the sentence (§2.3 step 1). It is still False at any record.
- **`held_kind()`:** exempts "not asked for: <held>" in `warning_reasons()` (nc `4978`), as `clock_kind()` does (nc `3972`).
- **`alerts_of()`** (nc `5910`), **`warns_of()`** (nc `5899`), new **`person_alerts_of()`**, **`plain_why()`** (nc `2331`), and **`alarms()`** (nc `5537`, the cause generalised): §2.9's routing and sentences. The day-0 line is conditional on `whose()`.
- **`close_verdict()`**: writes `ALERT_PERSON_FILE` beside `ALERT_FILE` and `WARN_FILE` (nc `5880-5881`), empty when there is nothing to say.
- **`weekly()`** (nc `6141`): §2.10.
- **Docstrings:**
  - the header (dev `26-30`: "a refusal on file, at any age, means no fetch tonight") gains "unless it is one the night tests itself";
  - the `when` row (dev `313-320`);
  - THE NIGHT'S CLOCK (nc `447-468`): "those three steps", the knock first;
  - ALERTS THAT REACH THE PERSON (nc `5840-5880`): the third check, and why;
  - a new section, THE NIGHT'S KNOCK.

**`src/ops/cloud.py`** (`2026-09-25.26` becomes `.27`)
- `lift_refusal()`, first in `state_up()` (§2.6);
- `pull_refusal()` and `send_refusal()` read `state/knocks.json`. A lifted sha is recognised at any age;
- `DRY_NEVER` gets `"knocks.json"`;
- docstrings at `1637-1640` ("a refusal is cleared by a person" adds "or lifted by the night's knock, which leaves state/knocks.json naming it"), `2049-2061` and `2754-2771`.

**`cloud_kit.json`**
- a state entry for `archive/knocks.json`;
- `refused.json`'s "what" (`:197-198`);
- `dry_run.state` unchanged (knocks.json is never in it).

**`.github/workflows/nightly.yml`, `weekly.yml`:** the two env lines each (§2.11). In `nightly.yml`, "Tell Healthchecks how the night ended" gains `HC_PERSON_URL: ${{ secrets.HEALTHCHECKS_PERSON_URL }}` and the three cases of §2.9. There is no new step and no `if` change.

**`preflight.py`:** `WORKFLOW_SECRETS` (nc `93229`) gains `HEALTHCHECKS_PERSON_URL`, and the new checks of §6.

**`netcheck.py`** (a separate commit)
- `ok = out.startswith("HTTP 2")`, and a body carrying the block page is not "through" (`:162`, `:196-198`);
- an HTTP error line reads "HTTP 403 -- the server ANSWERED, and said no";
- test 8, labelled "root", repeats test 4 (read_refusal): relabel it or drop it.

**`src/fetch/gc_db/fetch_day_db.py`** (`21-24`, `63-66`) and **`probe_db.py`** (`106-110`): docstrings only.
- "with no refusal on file" becomes "with no refusal a person must clear on file";
- `probe_db.py:109-110` becomes: "A refusal a person must clear holds this host too (the person's decision of <date>); one the night is testing does not, for 16 days at most".

**`versions.json`:** `python3 src/ops/inventory.py --bump-changed` in every commit.

**Not changed:**
- `classify()`;
- the two-drop rule outside the week after a lift, and the page counting as the first drop;
- `gc_lane.py`;
- `probe_db`'s hold;
- the night-timer;
- the `started` job;
- `TRIES_AFTER_DB` and `DB_AFTER_TRIES`.

**Configuration, the owner's (D6):** `.claude/hooks/guard.py:302-306` asks before `cloud.py clear-refusal`, `cloud.py send-refusal` and `netcheck.py`.
- Today it asks before `refusal.py --clear` but not before the command that actually frees the night.
- Checked offline with the guard's own `decide()` (read_refusal).

---

## 6. The checks, each failing without its rule

All run under `preflight.py --code` with fakes and no network, in the patterns of `_snapshot_stops` and `_nightly_runner`.

| # | Check (new or changed) | Asserts | Fails if |
|---|---|---|---|
| C1 | `_refusal_kinds` (new) | `note(kind="dropped")` with `GITHUB_ACTIONS=true`, ref main and both switches set writes kind, `machine=="github"`, `dry is False`, run_id; `whose()=="night"`. A person's in each of these cases: no `GITHUB_ACTIONS`; `DRY_RUN=true`; ref `refs/heads/dev`; ref `refs/heads/Main`; kind `"refused"`; **the 29 Oct record's exact bytes** (`{at, epoch, where, why}`); `NIGHT_KNOCK` unset or `ON `; `NIGHT_PERSON_CHECK` unset or `none`. **For every one of these person cases, `from_database(held=True)` on fakes refuses and asks nothing** | a field is not written; the machine, dry, ref or switch test is dropped from either door; a kindless record becomes resumable |
| C2 | `_refusal_ladder` (new) | With epoch 1793262435: due at `GRANITE_CLOCK_UTC=2026-10-30T08:23:00Z`; not due at E+15.99 h; after failed knocks, due at exactly +40, +88 and +160 h from each; after 4, a person's; at `since`+384 h, a person's; a 503 knock with `Retry-After` 50 h pushes the due time past +40 h; `retry_after` 161 h is a person's; `min(KNOCK_HOURS)*60 > (KNOCK_LATEST − daily start)` in minutes | a first rung ≥ 24 h or < 16 h; the cap or the 16 days removed; `Retry-After` ignored; a rung that allows two knocks in one window |
| C2b | `_refusal_relapse` (new) | `lifted[-1]` 100 h old with 2 knocks: a new `note(kind="dropped")` starts `current` with those 2 knocks, that `since` and `carried_from`; one more failed knock and then one carried relapse with a fourth make it a person's; a relapse noted at the carried `since`+385 h is a person's; a lift 169 h old starts a fresh chain (no knocks, a new `since`); `drops_allowed()` is 1 at 167 h after a lift and 2 at 169 h | the carry is lost (renamed, `RELAPSE_HOURS` 0, `current` written before `lifted` is read); the one-drop week is lost |
| C3 | `_refusal_unavailable` (new) | `unavailable()` is None for a 503 carrying `_BLOCK_PAGE`, a 429 and a 403; seconds for `Retry-After: 120` and for an HTTP date | the body is not read; 429 slips in |
| C4 | `_snapshot_stops` (changed, dev 81515) | The incident's sequence (page dropped, then `Docket.txt` dropped) writes `kind: "dropped"`; a 403 writes `"refused"`; a 503 with the block page writes `"refused"`; a bare 503 writes `"unavailable"` with its `Retry-After`, **and the run stops at the 503**. With a lift 10 h old in `knocks.json`: a dropped page ends the run after **one** request and notes; a dropped file after a whole page ends it with no `time.sleep(60)` and no second request for that file | a site passes no kind; 503 stops being an immediate stop; the week's one-drop rule is ignored |
| C5 | `_the_knock` (new; `snapshot_gencourt.py --knock` through `main()` on a faked opener) | exactly **one** opener call, to `BASE+"Counties.txt"`, with `UA`, never `PAGE`; the opener has no redirect handler. Answers: 195 bytes, **3 bytes (`b"\xef\xbb\xbf"`) and 0 bytes**, each over 200, give exit 0, `MARK` gone, `lifted[-1].text` equal to the old bytes, and `refusal` equal to the sha of the pre-knock bytes. The block page as 200, a 403, a 429, a 302 or a 503 with the block page each give exit 2 and `person` set. A bare 503, a drop, a timeout, a 404 or `<html>` with 200 give exit 1, a knock counted, still `"night"`. The opener raising `SystemExit` after `knocking()` leaves a "no answer" entry. **Zero** opener calls and exit 2 for: a record 2 h old; a kindless record; `DRY_RUN=true`; no `GITHUB_ACTIONS`; `NIGHT_PERSON_CHECK` unset; a clock at **11:30**, **12:30** and 14:00 UTC. AST: the `--knock` branch calls `refusal.check(…, knock=True)` before `knock()`, and **no other call anywhere in the repository passes `knock=True`** (beside `_every_fetcher_checks_refusal`, nc preflight `77686`) | a second request or the page; a redirect followed; a browser UA; an empty export counted as a failed knock; the sha taken after the knock; deleted without keeping; the attempt written only after the answer; the gate removed, moved after the request, or let past 11:18; a second caller of `knock=True` |
| C6 | `_nightly_knocks` (new; `nightly.py --runner` on fakes, as `_nightly_runner`) | A due record at 08:30 UTC gives `--knock` once, then the normal snapshot, installed, `v["knock"]` starting "lifted". **A lift at 11:17 followed by an empty export and a standing `probe_db` hold: exactly one `SNAP`, no `time.sleep(EMPTY_WAIT*60)`, nothing installed.** At 11:30 (+42 min passes 12:00) and at 14:33: no knock, "not asked for", a database night. Not due: no knock, a database night, the why naming the due date. **Run 108's kindless record kept as it is** (dev 82537-82547): no knock, no database, "FETCH DEFERRED: a refusal is on file", exit 1. `--dry-run` / `--new-term`: no knock. Knock rc 1: a database night, no snapshot. Knock rc 2: nothing more, no database, the alert. `NIGHT_KNOCK` `off`, `ON ` or unset, or `NIGHT_PERSON_CHECK` not `set`: no knock, no database. A record past 4 knocks or 16 days: no knock, **no database**. `warning_reasons()` of a held night's and a lift night's warnings is `[]` | the night never knocks, or knocks twice; the clock gate is gone; a second export try on a lift night; a kindless or a person's record opens anything; the switch or the third check is ignored; a held or lifted night holds the gate |
| C7 | `_nightly_falls_back` (new runs; dev 89426) | **310h**: a due-later `dropped` record gives no `SNAP`, one `DBASK`, installed, `fetch` starting "held", no `fetch_lsrs.py` or `fetch_calendar_archive.py` call, clean, publishable. **311k**: `refuse_on=1` writing `kind:"dropped"` gives `order()==[SNAP]`, no `DBASK` that night (rule A). Runs 310, 311, 311b and 317 and the direct `from_database()` call (dev 90012-90130) **unchanged and green** | the held path asks the export or the lists; the drop night goes to the database before the record reaches the bucket |
| C8 | `_cloud_lift` (new, folder bucket, beside `_cloud_state_and_site` dev 55276) | The bucket holds R, `state-down` took sha(R), and local `knocks.json` has sha(R) lifted, on GitHub and main: `state_up` puts R under `replaced/<day>/`, `state/refused.json` is gone, `state/knocks.json` is sent, and a second `state_up` changes nothing. Nothing moves when: the lifted sha ≠ the bucket's; the bucket changed since `state-down`; `only=` (a dry night; and `knocks.json` not sent); no `GITHUB_ACTIONS`; ref ≠ main; `DRY_RUN=true`. A relapse (new local record plus a lift of the old): old moved, new sent. "Absent here is never removed there" still holds without a lift. `"knocks.json" in DRY_NEVER` and not in `dry_run.state` | delete without moving; lift on a dry night or off main; a lift without compare |
| C9 | `_cloud_pull` (changed, dev 58726) | A laptop copy under 24 h, the bucket holding none, and the bucket's `knocks.json` lifting its sha: the lift line, not a failure, and the copy **stays** on file; `send_refusal` returns done without sending; the unsent marker is lifted. **The same copy 40 days old: the lift line, never the "send-refusal sends it" advice** | pull ignores the bucket's lift (the `2801-2813` trap) at any age; the laptop's copy is set aside |
| C10 | `_refusal_check_laptop` (new) | A `machine:"github"`, `kind:"dropped"` record 30 h old: `check()` exits 2. A kindless record 30 h old passes, as today | the any-age rule is dropped, or spreads to kindless records |
| C11 | `_alarm_stays_able_to_ring` (changed, dev 109839) | A held, clean night: `alerts_of()==[]`, `person_alerts_of()==[]`, and `warns_of()` holds the held line. Day 0 (not clean, the night's): `alerts_of()` holds the record's line, naming the next knock date, "nothing is needed from you on GitHub's side", the "refusal is yours" check, and the laptop's `refusal.py --clear`; `person_alerts_of()==[]`. **Day 0 with `NIGHT_KNOCK=off`, and again with `NIGHT_PERSON_CHECK` unset: `alerts_of()` names `clear-refusal` and no knock date; `person_alerts_of()` holds the line.** A person's: both hold it, naming `clear-refusal`. A lift: neither | the routing in §2.9 changes; the switch leaves the alert promising a knock |
| C12 | `_night_clock` (changed, nc 92277) | `gated == ["knock", "take_documents", "take_lsrs"]` (nc 92374); the docstring sentence is "those three steps" | a fourth caller, or the knock ungated |
| C13 | `_knock_export_minutes` (new) | `EXPORT_MINUTES*60 ≥ PAGE_TIMEOUT + (len(targets())+1)*(120 + 1.25*delay) + 60`, read from the snapshot's own constants and `--delay` default; **`refusal.KNOCK_LATEST` in minutes `== ASK_UNTIL − (KNOCK_MINUTES + EXPORT_MINUTES)`** | a timeout grows past the allowance; the child's limit and the parent's part |
| C14 | `_nightly_weekly` (changed, nc 84267) | Under a `dropped` record the night tests, the four database pieces are asked, `fetch_committees.py` is not, the weekly is clean, and no `--knock`. Under the same record past 16 days: nothing asked | the weekly knocks, or asks the website while held, or the database after 16 days |
| C15 | `_netcheck_verdict` (new) | netcheck's verdict, on a faked `HTTPError(403)` and a 200 block page, does not say "Everything got through" | 403 counted as passing again |
| C16 | `_workflows_night_knock` (new) | both workflows set `NIGHT_KNOCK` from `vars` with `'on'` as the fallback, and `NIGHT_PERSON_CHECK` from whether `secrets.HEALTHCHECKS_PERSON_URL` is set; nothing else reads either; `nightly.yml`'s "Tell Healthchecks how the night ended" sends `$env:HC_PERSON_URL/fail` with `logs/alert-person.txt` as the body when that file is non-empty, and a plain ping when it is empty | the switch or the coupling is lost; the third check is not pinged |
| C17 | `_assistant_guard` (changed, dev 67182; only if D6) | `cloud.py clear-refusal`, `cloud.py send-refusal` and `netcheck.py` give `ask` | |
| C18 | `_person_check_rings` (new; `--runner` and `--close` on fakes, reading the three alert files each night as the workflow would ping) | **Sequence 1:** a clean night, day 0 (drops), day 1 (knock answered with the block page). The third check's file is empty, empty, then non-empty: up, up, `/fail`, a change. The night's file is non-empty on days 0 and 1: no change on day 1. **Sequence 2:** day 0, then database nights to the 7th (the night's file non-empty from the 7th, `DB_NIGHTS_MOST`), then the 4th failed knock on day 14. The third check's file is empty through day 13 and non-empty on day 14. **Sequence 3:** day 0, then `NIGHT_KNOCK=off` on day 2: non-empty on day 2 | the "this is yours" moment fails to change the third check's state |

**Left alone and must stay green:**
- `_nightly_guards` (dev 81660: a kindless old record defers);
- `_nightly_runner` 108;
- `_every_fetcher_checks_refusal`: the knock lives in `snapshot_gencourt.py`, which already calls `check()`, so there is no new script and no exemption;
- `_every_fetcher_notes_refusal` (`classify()` unchanged);
- `_lane_daily`; `_night_window`; `_workflows_permissions`.
- `_workflows_secrets` (nc `93372`) stays green once `WORKFLOW_SECRETS` names the new secret.

**A log reader** (beside `_nightly_log_findings`, dev 81789, and `_nightly_logs`) flags, from the night logs on disk:
- two knock lines on one UTC date;
- a knock line in a dry run's log;
- a knock line timed outside 08:00-11:18 UTC.

These are the misbehaviour signals in §11, made into a check.

---

## 7. Documents, and the CLAUDE.md wording

**Each changes in the commit that changes the behaviour it describes:**

| Document | Lines (dev) | Change |
|---|---|---|
| `README.md` | 344-353 | the refusal paragraph |
| `ARCHITECTURE.md` | 113-117; 266-272 | the fetch while held. "its recovery is the sign it was cleared" adds "... or lifted by the night's knock". The same sentence still lists "a night the gate holds for approval" among alerts, which moved to the warnings on 22 Oct (existing drift) |
| `CONTRIBUTING.md` | 24-31 | |
| `SECURITY.md` | 93-98 | |
| `watchers/README.md` | 71-83 | pull's lift line; the lane still stops |
| `cloud_kit.json` | 197-198, the new entry | |
| docstrings | `refusal.py`, `nightly.py`, `snapshot_gencourt.py:683`, `cloud.py`, `fetch_day_db.py`, `probe_db.py` | §5 |
| the operator checklist | where the Healthchecks secrets are listed | the third check, what it means, and that the method is off without it |

**CLAUDE.md is the owner's file.** Proposed replacement for lines 74-79. It also corrects two existing errors there:
- "twelve seconds": `refusal.py:22-24` says fifty-four;
- "holds the fetch lane for 24 hours": the lane holds at any age, `gc_lane.py:402-406`.

> **A refusal outlives the run that met it.** `refusal.py` records one in
> `archive/refused.json`, with what kind it was. It exists because a drain that
> met two 403s stopped itself correctly, and a chained run started asking the
> same address for a docket fifty-four seconds later. The lane, and GitHub's
> night, stop at a refusal for as long as it is on file; a fetch started by hand
> here stops for 24 hours, and for as long as it is on file if GitHub's night
> met it. One kind is the night's to test, by the person's decision of <date>:
> two dropped connections, timeouts, or a 503 that is not the firewall's page,
> met by GitHub's night on `main`. That night ends as before. For up to sixteen
> days the nights after build from the General Court's database, and ask its
> website one request, for `dynamicdatadump/Counties.txt`, from inside the
> night's own job, between 08:00 and 11:18 UTC: the next morning, and then
> after two, four and seven more days. Any answer that is the file lifts it
> (moved into `archive/knocks.json`), and the night goes on; for a week after,
> one dropped connection ends the export. Everything else -- a 403, a 429, the
> firewall's page or a redirect, on a night or to that request; a fourth
> request unanswered; sixteen days; any refusal met on this laptop or by a dry
> run; any record from before <date> -- is a person's to clear, as it always
> was, and stops the database too: `python3 refusal.py --clear` here and
> `python3 src/ops/cloud.py clear-refusal` for the night's, after
> `netcheck.py` has said what kind of refusal it was. The Healthchecks check
> `HEALTHCHECKS_PERSON_URL` emails the moment a refusal becomes a person's, and
> the night tests nothing itself unless that check is set and the repository
> variable `NIGHT_KNOCK` is `on`.

**CLAUDE.md:92-98** (the `fetch_*_db.py` paragraph) gains one sentence:

> The night reads that host by itself, for sixteen days at most, while a refusal it is testing stands, and never while one a person must clear stands.

---

## 8. Landing: night-clock, the 1 November release, and the order

1. **Now, independent of this work: the owner clears the standing record by hand.**
   - It has no kind, so nothing here will ever lift it.
   - Until it is cleared, every night is stale and main's newer code does not publish (read_night §3).
   - The order: `python3 netcheck.py`, reading its printed table and not its last line, which counts a 403 or the block page as "got through" (`netcheck.py:162`, `196-198`). Then `python3 src/ops/cloud.py clear-refusal` and `python3 refusal.py --clear`.
   - The manager's netcheck from a cloud container about 8 hours later said nothing about GitHub's runner (a guess that runner addresses differ).
2. **1 November: the release** (dev → main). Nothing of this is in it.
3. **Early November: `feat/night-clock`** (now `22d19e4`) merges to dev and goes live on its own approval.
4. **This work is built on a branch `feat/night-knock` cut from `origin/feat/night-clock`'s tip.**
   - It needs `asking_left`, `seconds_left`, `run(timeout=)` and `RUN_KILLED`, and it changes `_night_clock`'s pinned list.
   - When night-clock is merged into dev, merge dev into `feat/night-knock`.
   - Merge `feat/night-knock` into dev only after night-clock is in dev.
5. **On dev:**
   - a full `preflight.py`;
   - `src/ops/handoff.py`;
   - one dry run on dev. It must show that a dry run neither knocks, nor lifts, nor sends `knocks.json`, and its log must print `NIGHT_PERSON_CHECK` as `set` once the owner has added the secret (this confirms the §2.11 guess). Check its log and the bucket's `state/` after it.
   - A dry run cannot exercise a knock or a lift, by design. Nothing should provoke a refusal to test one.
6. **The owner creates the third check and the secret (D5) before the merge to main.** Without it the merge changes nothing (§2.11): every record stays a person's, as today. With it, the first real night after the merge pings it once and leaves it "up".
7. **To main only on the owner's word**, after D1 to D5 are answered.
   - It is a release for the gate, so it needs a clean dry run of the same commit within 48 h, or the person's approval (dev `4583-4603`).
   - The first real exercise is the next real drop.
   - If D3 (the database) is declined, commit 7 below is left out and the rest stands.

---

## 9. Build plan, in small commits

Each commit:
- bumps stamps (`inventory.py --bump-changed`);
- passes `preflight.py --code`;
- carries its own docs;
- leaves the night's behaviour safe if it were the last commit.

1. **The record says what it was.**
   - `refusal.note()` fields, `unavailable()`, `knock_on()`, `whose()`;
   - the kinds at the snapshot's and `fetch_committees`' sites;
   - C1 (its `whose()` part), C3, C4 (its kind cases).
   - No reader acts on a kind yet, so behaviour is unchanged.
2. **The ladder and the knock's state.**
   - `knocks.json`, `knocking()` / `knocked()`, the lift on disk (`lifted` never pruned), the relapse carry, `knock_due()`, `knock_schedule()`, `drops_allowed()` and its two readers, `force()` and `main()` status;
   - C2, C2b, C4 (its one-drop cases).
   - Still inert: nothing lifts yet, so `drops_allowed()` is always 2.
3. **The bucket knows a lift.**
   - `lift_refusal()`, `pull_refusal()` / `send_refusal()` reading `state/knocks.json` at any age, `DRY_NEVER`, `cloud_kit.json`;
   - C8, C9.
   - Inert until a lift exists.
4. **The knock child.**
   - `snapshot_gencourt.py --knock`, `check(knock=True)` with `KNOCK_LATEST`, the no-redirect opener, the answer rules (any size);
   - C5.
   - Nothing calls it yet.
5. **The third check and the switch.**
   - `person_alerts_of()`, `ALERT_PERSON_FILE` in `close_verdict()`, the two env lines in both workflows, the Healthchecks step's third ping, `WORKFLOW_SECRETS`, the operator checklist;
   - C16, C11 (its switch-off cases).
   - Useful on its own: from this commit every record that is a person's (which, until commit 6, is every record) emails through the third check.
6. **The night knocks.**
   - `knock()` wired before the export, `asking_left(42)`, the kill, the lift night's single export try;
   - the `gc_quiet()` sentence; the day-0 and "a person's" alerts;
   - `_night_clock`'s list, the THE NIGHT'S CLOCK and THE NIGHT'S KNOCK docstrings;
   - C6 (its knock rows), C11 (the rest), C12, C13, C18 (sequences 1 and 3).
   - From here a drop-type record lifts itself. Held nights still build nothing.
7. **The database while held** (D3).
   - The held path, `from_database(held=)` reading `whose()`, the `db_open` gates, the held lines, `KIND_WEB_HELD`, `held_kind()`, `v["web"]`, `weekly()`, the generalised `DB_NIGHTS_MOST` sentence, the `fetch_day_db` and `probe_db` docstrings;
   - C1 (its gate part), C6 (its database rows), C7, C14, C18 (sequence 2).
8. **The laptop tightening:** `check()` at any age for a GitHub record with a kind; C10.
9. **netcheck's verdict** (and test 8's label); C15.
10. **Docs and the log reader:** README, ARCHITECTURE, CONTRIBUTING, SECURITY, `watchers/README.md`, and the log-reader check. The proposed CLAUDE.md text goes to the owner, not into the commit.
11. **The guard rows (D6), on the owner's word only;** C17.

**Effort, a guess:**
- code about 700 lines;
- preflight about 950;
- three to four working days, with a review round between 6 and 7.

---

## 10. Risks

1. **A true block that looks like drops** (`netcheck.py:13-19` describes exactly that).
   - If every knock comes from the blocked address: 2 + 4 single 195-byte requests over 14 days, with our own User-Agent, at least 16 h apart, and database nights.
   - If runner addresses vary (a guess): still at most 6 requests at the blocked address per chain (§3), and ordinary nights from the others.
   - *Guess:* whether a firewall's ban timer restarts on contact. Nothing records a block's length, trigger or answer beyond the two the project provoked (read_history).
2. **A lift may come from a different address.** *Guess:* GitHub runner addresses change from night to night, and nothing records them.
   - The knock cannot tell "the block ended" from "tonight's runner is elsewhere".
   - After a lift the night asks only its ordinary traffic, the same as the 50 healthy passes since 30 September, and for a week one drop ends it.
   - This is why 403, 429 and the block page stay a person's.
3. **The database during a block.** About 170,000 rows a night from PublicSQL, for 16 days at most.
   - The IT office okayed that host ("No problem hitting PublicSQL during a session as it doesn't touch the website").
   - `probe_db` holds it after one failed connection.
   - *Guess:* whether it sits behind the same perimeter as the website.
4. **The database compared with itself** after many held nights (dev `2607-2609`). Bounded by the `DB_NIGHTS_MOST` alarm (and its email) at 7 nights, and by both doors closing at 4 failed knocks or 16 days.
   - A hold across the start of a session year leaves the new year's rows out, as a warning, until the export returns (`dayfiles_from_db.py:374-377`). At most 16 days.
   - The website-only files (`Members.txt`, the lookups, the bill requests, the lists) age for the length of the hold.
5. **One stale day per outage**, from rule A. Also a stale day on any relapse night, and on a night in the week after a lift that meets one unlucky drop. That happened on none of the 30 nights read.
6. **The knock's record can be lost** if the runner dies between the knock and `nightly.py`'s exit. The next night may then knock one rung early: still at most one a day, and the 16 days still hold.
7. **The gate can still hold** the first lift night or a database night: the release proof after 48 h, more than 600 rows, a new warning kind. The new kinds are exempt (C6), and daily database nights keep each night's change small.
8. **`Counties.txt` renamed or removed:** 404 knocks, a person's after four, and the alert quotes the 404. *Guess:* whether asking it rebuilds the county table ("data refreshes on file access"); if it does, that is ten rows.
9. **The timer must start the night in the morning** for a knock. Late nights take the database, and the 16-day bound ends it.
10. **Healthchecks.**
    - The third check carries the one email that needs action. The method is off without it, and C18 drives the sequences in which it must ring.
    - It rings only if the night runs `--close`. A runner that dies first leaves it unchanged until the next night.
    - The warnings' check is likely already down (§2.9), so middle notices may be silent.
    - Day 0 of a person's record sends two emails, one from each check. That is accepted as the cost of never losing one.
11. **Dry runs cannot exercise the knock or the lift.** The proof is the fakes until the first real drop.
12. **The standing record must be cleared by hand.** A drop before this lands still costs a person.
13. **Doubled work on the laptop:** after a lift, the laptop still needs `refusal.py --clear` (by design). Its next pull and the day-0 email say so.

## 11. What would tell us it is misbehaving

| Sign | Where | Meaning, and what to do |
|---|---|---|
| Two knock lines on one UTC date, or a knock outside 08:00-11:18 UTC | `logs/<day>/nightly-<day>.log` in R2; the log-reader check | The one-a-day bound broke. Set `NIGHT_KNOCK` to `off` and read the code |
| A knock line in a dry run's log, or `state/knocks.json` changed by a dry run | the dry run's log; `replaced/` | The dry-run locks failed. `off`, then fix |
| `state/knocks.json` shows a lift while `state/refused.json` still holds the same sha the next day | the bucket | The compare-and-move did not run (the night's page says why). The next night knocks again; safe, but find out why |
| The laptop's pull FAILs "IS NOT IN THE BUCKET", or advises send-refusal, for a record the night lifted | pull's output | `pull_refusal` is not reading the lift. Do **not** send-refusal; clear by hand |
| `carried_from` chains, or relapse lines several nights running | `knocks.json`, verdict `web` | A flapping server. The ladder ends it at four. If it repeats every outage, think about a longer first rung |
| A knock answered `404` | verdict `web.knocks` | `Counties.txt` moved. Pick another of the 14 (a later decision) |
| The night's check flapping down/up daily | Healthchecks | Relapses, or a database that alternates. Read the run pages |
| The third check never pinged, or "new" in Healthchecks after the merge | Healthchecks; the night's log line for the step | The secret is unset or the step is wrong. The method is off meanwhile (§2.11), so nothing is unsafe; fix the secret |
| Database nights past 16 days, or any database night under a person's record | the run's page; verdict `files_from` | The single gate failed. `off` at once |
| Any web request on a held night other than the one knock | the night's log ("the day's bulk files" or "next session's bill requests" on a held night) | A gate is wrong. `off` at once |
| A second export try on a lift night | the night's log ("try 2 of") | The lift-night rule failed. `off`, then fix |

---

## 12. The owner's idea, weighed

> "the live updates may assist ... the nightly can resume whenever the live shows it's up again"

**Where it cannot help: it cannot show the website is back.**
- The live Worker (`/tmp/claude-0/audit/wf16/design_final.md`) reads PublicSQL and YouTube and never gc.nh.gov (`:43`, `:59-60`, `:743`).
- A healthy database proves little about a web server that dropped.
- It reads from Cloudflare's addresses. A test it made would say nothing about GitHub's runner, and would be a third machine asking beside the night: the two-at-once pattern behind the second block.
- On 29 October it would have read nothing. Off-season, outside January to June and with no sitting within 14 days, it is Off (§2.3 there, `:341-347`), and it never starts inside the night's window.
- It writes its own bucket, which the night holds no credentials for (`nightly.yml:334-337`).
- Its SQL half is unfinished (`live/tds`, 185a9f2, WIP).

**Where it is right, and what this method takes from it:**
1. **"Light, frequent signs decide when the heavy job resumes."** That is the knock's shape. It is moved to the one place where it proves something: from the machine that will fetch, under the night's lock, seconds before the export.
2. **"The live layer's door is healthy when the website is not."** That door, PublicSQL, is part 3 of this method. The night uses it itself, so the site stays current while the website's question waits for the next morning. The owner's idea points straight at it.
3. **During a sitting, Live Now and the live votes keep the session day current** between nights, whatever the night's website does. That covers rule A's stale day on the days it matters most.
4. **From January to June, the Worker's heartbeat** is an independent sign that the General Court's database is up. It is useful to a person deciding whether to clear a refusal by hand. The night does not read it.
5. **Its holds already expire by themselves** (wf16 design §2.6, "None needs a person to clear it"). The knock carries that idea to the website, more cautiously.

---

## 13. Left out on purpose

- **The database on the morning of the drops** (design_fresh; the freshness judge).
  - The site would be current that same morning, but the record would reach the bucket only after the database night and the build (`nightly.yml:449-459` runs after `nightly.py` exits).
  - To have both, the record must be sent mid-run. That means either R2's keys in the night step, which exposes them to every child of `nightly.py`, or a second night step after the refusal step, with the night's outputs (`built`, `publishable`, `review`, nc `nightly.yml:249-259`) and `--close`'s outcomes coalesced.
  - Worth revisiting after the first real outage if a stale day hurts. The live layer covers sitting days meanwhile.
- **Same-morning knocks at 60 and 90 minutes** (design_same-morning). This is the "wait a bit and try again" of `refusal.py:35-38`, from the address that was just dropped, with the record held off the bucket for hours.
- **Letting the page's drop not count**, so `Docket.txt` gets its one retry (`snapshot_gencourt.py:587-588`). It would add a request to a run already being dropped, with no evidence it would have helped. With the knock, the strict rule costs a day, not an indefinite stop.
- **netcheck, or a new script, as the knock.** netcheck makes 8 requests to two hosts with browser User-Agents and counts a 403 as passing. A new script would need its own exemption in `_every_fetcher_checks_refusal` (dev 77741).
- **The database for laptop-written or dry-written records** (design_fresh's table). The safety judge: never on a kind unmerged code wrote.
- **Building main's code on a held night with no database** (read_night §5d): a separate decision.
- **Database nights past 16 days, held each night for approval** (the red team's alternative for its fourth finding). They would keep asking PublicSQL during what may by then be a block, which §4 rules out, and would need a click every day.
- **A signal for the laptop lane's stop.** The lane cannot ask again until a person runs `pull`, and that pull prints the lift line (§2.6).
- **A cap on chains across weeks.** Each new chain is a new outage and sends a new day-0 email, because the night's check was up in between. The person hears every one.

## 14. Where this departs from the designs and the judges, and why

| Point | Took | Changed, and why |
|---|---|---|
| Knock target, opener, gate placement | minimal: `Counties.txt`, no redirect, `check(knock=True)` first | The child keeps its own 11:18 limit, and only one caller may pass `knock=True` (red team) |
| What lifts | — | Any 200 that is the file, whatever its size (red team: an empty export over 200 on 7 of 29 October nights) |
| `EXPORT_MINUTES` | — | 40, not 36. The retried file's own request was missing (safety judge); C13 holds it to the constants. The "both end before 12:00" claim is stated for the computed worst case only. A lift night has one export try (red team) |
| State file | minimal's `knocks.json`; `refused.json` write-once | `current` and `lifted` split so a relapse keeps both; `lifted` holds the exact text and is never pruned (red team) |
| Database while held | fresh, Part 2 | Only for records GitHub's main, non-dry night wrote. Never on the drop night (rule A). **Closed whenever the record is a person's**, 16 days and 4 knocks included (red team: the bound was not real) |
| 503 | minimal | Never capped (fresh capped at 168 h). The body is read for the block page |
| Escalation | — | **A third check, always, and the method off without it** (red team: the night's check is often already down when the record becomes a person's). Middle notices go to the warnings' check and the page; the day-0 email states the whole schedule |
| A never-tested record | — | **New:** 16 days, then a person's (minimal's risk 6 noted the timer dependence; nothing bounded it) |
| Laptop hand fetches | — | **New:** any age for a GitHub record with a kind (safety judge's gap) |
| The laptop's copy after a lift | minimal: kept | fresh's set-aside rejected (safety judge) |
| After a lift | — | **New:** one drop ends the export for a week (red team, extended from the lift night to the week) |
| Workflow | no new step or `if` (freshness judge) | two env lines per workflow, and one more ping in an existing step |

## 15. Guesses, said plainly

- Whether the 29 October knock would have been answered. The only sign is one unlogged netcheck from another machine about 8 h later.
- That GitHub runner addresses change from night to night.
- Whether contact lengthens a firewall ban.
- Whether PublicSQL sits behind the website's perimeter.
- That IIS's 503 means a recycling pool.
- That asking `Counties.txt` rebuilds only that table.
- The publish check's period (about two days, from a comment).
- Whether `HEALTHCHECKS_WARN_URL` is set at all.
- That `${{ secrets.X != '' && 'set' || 'none' }}` evaluates as written in a workflow-level `env` (the first dry run's log confirms it, §8 step 5).
- Every number in `KNOCK_HOURS`, `KNOCKS_MOST`, `HELD_MOST_HOURS` and `RELAPSE_HOURS`. They are `probe_db`'s tested shape moved 4 h earlier, and are not measured against gc.nh.gov.
- The effort.

## 16. Notes on the readers' findings

- **A dry run cannot overlap a main night's job.** The run-level groups differ (`nightly.yml:143-145`), but the night job's own `concurrency: gc-night`, `cancel-in-progress: false` (`nightly.yml:246-248`; `weekly.yml:102`) serialises every night and weekly job. That is what makes "one knock a run" a bound.
- **The night-clock tip is `22d19e4`**, not `84a81ee`. The functions this needs are unchanged.
- **Doc drift found:**
  - CLAUDE.md:74-77 (24 h; twelve seconds);
  - `refusal.py:861-863` ("no longer stops anything");
  - `snapshot_gencourt.py:683` ("for a day");
  - `nightly.yml:100-106` against `620-623` on whether "production" has a required reviewer (GitHub's settings could not be read);
  - `cloud_kit.json` on `last-dry-run.json` (read_holds).

  The first three are fixed by this work; the last two are not.

---

## 17. Red team

Each finding was checked against the code or the bucket's logs before it was taken. All ten hold. Two are taken in a changed form (6 and 10), and one point of reasoning in the tenth is corrected.

| # | Finding | Checked | What changed |
|---|---|---|---|
| 1 (high) | The "this is yours" email is lost when the night's check is already down | **Holds.** Healthchecks writes on a change (nc `5846-5849`). The step sends `/fail` whenever `alert.txt` has a line (nc `nightly.yml:589-591`). `clean` includes the alarms (nc `5583`), and `DB_NIGHTS_MOST` is an alarm (nc `5541`). So on 29 October's dates the night's check is down from 5 November, and on day 1 after day 0 | The third check, always (§2.9). The method is off without it (§2.11, condition 7), so a record the night tests always has that email available. The day-0 body says "nothing is needed from you on GitHub's side" only when the night tests the record (C11). C18 drives the two sequences the red team named, and a third for the switch |
| 2 | An empty export counts a healthy server as down | **Holds.** `Counties.txt` was "not a data file (0 bytes)" or "(3 bytes)" over 200 on 1, 2, 3, 4, 5, 9 and 12 October, 7 of 29 main nights (the bucket's night logs), after the page | Any 200 without the block page, not a redirect and not HTML lifts, whatever its size (§2.4). The 0- and 3-byte bodies are C5 lifts. An HTML 200 stays a failed knock: a maintenance page is an outage |
| 3 | No check pins the relapse carry | **Holds.** C2 and C8 did not assert it, and without it a flapping server is unbounded | C2b (§6): the carry, the fourth knock in a chain, `since`+385 h, and a fresh chain at 169 h |
| 4 | The database has no end date | **Holds.** The alarm "does not stop the night" (nc `5537-5539`), the fallback kinds never hold the gate (nc `977-995`), and the held nights skip the bill requests and lists (nc `1701`, `1717`, `1729`) | One door (§2.2): the database is open only while the night tests the record, so 16 days and the fourth knock close it. §2.3 and §4 now say so truthfully. The alternative (approval each night past 16 days) is left out (§13) |
| 5 | The off switch leaves the alert promising a knock | **Holds.** `knock_on()` was read only in `nightly.py`; `whose()` did not read it | `knock_on()` moves to `refusal.py` and is condition 7 of `whose()`. Off means a person's for the gates, the wording and the routing (§2.11). C11 and C18 sequence 3 cover it |
| 6 | The laptop's lane stays stopped after a lift, and `lifted` ages out after 30 days | **Holds** for the wording and the 30 days (`cloud.py:2808-2813`) | Taken: `lifted` is never pruned; pull's lift line at any age, never the send-refusal advice (C9); the day-0 email and the lift line name the laptop's clear (§2.9). **Not taken: a new signal for the lane's stop.** On the stood-down laptop no request starts after a night window until a person has run `pull` (`refusal.gc_turn`, `refusal.py:730-744`). The lane's own header says "reading the bucket is a person's command here, not the lane's" (`gc_lane.py:46-54`). So a person sees pull's line before the lane can do anything. `laptop_share_behind` (nc `3755`) is the existing backstop |
| 7 | `db_door()` repeats `whose()` and is tested for one case | **Holds** | `db_door()` is gone; `from_database()` reads `whose()` (§2.2). C1 asserts the database refuses for every person case |
| 8 | `check(knock=True)` is a bypass any caller could use, and the child allows 13:30 | **Holds** (`refusal.py:522`: the daily window ends 13:30) | `KNOCK_LATEST` 11:18 in the child, pinned to the parent's 42 minutes by C13; 11:30 and 12:30 cases in C5; an AST case that only the `--knock` branch passes `knock=True` (C5) |
| 9 | A lift night can ask after 12:00 | **Holds.** A `probe_db` hold returns `stop("held")` (nc `3115`), which is not `DB_LOOKED_WRONG` (nc `2716`), so nc `1689` sets `last` to 2 and nc `1695` waits 30 minutes | The lift night's export has one try. The loop breaks; setting `last` alone would be undone at nc `1689` (§2.3). C6 has the case |
| 10 | The "6 in 14 days" ceiling assumes every knock fails | **The concern holds; the 4 × 17 does not.** A blocked address drops from its first request (run 151's log 1657-1658; `netcheck.py:13-17`). Under today's rule its relapse night costs 2 requests (page, first file), not 17. 17 is a server that answers the page and most files, and is not a block's signature | Taken further than proposed: one drop ends the export for the **week** after a lift (`drops_allowed()`, §2.7), not only on the lift night. The cost is measured: the 60 s retry ran on none of the 30 nights from 30 September to 29 October. With it, the blocked address sees at most 6 requests per chain, whether or not runner addresses vary (§3). The flapping row is restated (at most 16 on a lift night, one unanswered). for_owner.md now states the block case |
