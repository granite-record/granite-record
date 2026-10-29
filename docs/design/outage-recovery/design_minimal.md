# A night that heals after a passing outage: the smallest safe change

Read-only design, 29 October 2026.

**Code read:**
- `dev` at 4590795. That is 0702100 plus one page-text commit, and it touches none of the files below.
- `origin/feat/night-clock` at 22d19e4, which is 84a81ee plus a merge of dev and stamps.

**Evidence:**
- run 151's log (`logs/2026-10-29/nightly-2026-10-29.log`), its verdict (`state/last-night.json`) and the refusal record (`state/refused.json`);
- the 28 October night log, read for file sizes;
- the four readers' reports in this folder (`read_refusal.md`, `read_night.md`, `read_history.md`, `read_holds.md`).

Nothing asked the General Court, the SQL host or YouTube. Nothing tracked was edited. Bare line numbers are dev's, unless "nc" marks the night-clock branch.

**"Guess"** marks anything the code, the logs or the history do not show.

---

## 0. On one page

**The method.** GitHub's night tests some refusals itself, as one knock:
- **Which refusals:** two dropped connections or timeouts, or an HTTP 503 that is not the firewall's page, met by the night itself.
- **The knock:** one request for `Counties.txt`. The night asks for this 195-byte file every night anyway.
- **Where it runs:** inside the night's own job and lock, and only between 08:00 and 12:00 UTC.
- **When:**
  - the first knock is on the next night;
  - if nobody answers, the next knocks come after two, four and then seven more nights;
  - after a fourth knock goes unanswered, the refusal becomes a person's.

**When the file comes back whole:**
- the refusal is lifted. It is moved aside, never deleted;
- the lift is written into the bucket, so that neither machine puts the refusal back;
- the night then carries on exactly as it does today.

**What stays a person's, as today:**
- a 403, a 429, the firewall's block page or a redirect, whether met on the night or on the knock;
- a refusal met on the laptop or by a dry run;
- every refusal recorded before this change, which carries no kind.

**What does not change:**
- the laptop and its lane;
- the "another door is a person's" rule for the database;
- the workflow file;
- the approval gate;
- `classify()`.

| | |
|---|---|
| New scripts, machines, secrets or workflow steps | none |
| New state file | one, `archive/knocks.json` (R2 `state/knocks.json`) |
| Code files changed | `refusal.py`, `snapshot_gencourt.py`, `nightly.py`, `fetch_committees.py`, `src/ops/cloud.py`, `cloud_kit.json` (plus `preflight.py` and `versions.json`) |
| Requests the knock can ever make | at most 1 a day, and at most 4 per outage |
| Depends on | `feat/night-clock` (`asking_left`, `seconds_left`, `run(timeout=)`), so it is built after that branch merges |

**What it would have done on 29 October.**
- **30 October, about 08:27 UTC:** one GET of `Counties.txt`. If answered, the night runs as on 28 October, and the site is one day stale instead of stale until a person acts.
- **Whether it would have been answered:** a guess. The only evidence is the manager's unlogged netcheck from a cloud container about 8 hours after the refusal.
- **If not answered:** knocks on 1, 5 and 12 November, then a person's.

**The record standing now is not covered.** It has no `kind` (`state/refused.json`: `{at, epoch, where, why}` only), so under this design it stays a person's to clear. **Clearing it now is the owner's call.** The command is `python3 src/ops/cloud.py clear-refusal`, after reading netcheck's printed table, because netcheck's last line counts a 403 as "got through" (`netcheck.py:92`, `:114`, `:162`, `:196-198`).

---

## 1. Drop, block, 503: what can be told apart, and what cannot

**A drop cannot be told from a block by the answer.**
- On 29 October two connections were closed without a byte: `RemoteDisconnected`, log lines 1657-1658.
- That is the same on the wire as the repository's only first-hand description of a block (`netcheck.py:13-19`: "the server accepts the TCP connection and closes it without sending a byte").
- No firewall block page has ever been captured. Every "Web Page Blocked / Attack ID" in the repository is a preflight fixture (read_history §3B).

**What did differ is circumstance:**

| | What came before | How long it lasted |
|---|---|---|
| Both recorded blocks | something we did: about 1,000 guessed filenames; two workers at once | "days" (CLAUDE.md:55-58) |
| 29 October | nothing: the night's first two requests, 24 h after GitHub's last | under 8 h, seen from another address |
| 11 September | | under 61 min |
| 2 October | | about 8½ h |
| 3, 4, 5, 9 and 12 October | | gone by the next night |

On GitHub's machine from 30 Sep to 29 Oct, 51 passes of the export met exactly one drop, and 23 export failures provoked no refusal (read_history §1).

**So the rule cannot decide "outage" from the answer. It can do this instead:**
- treat a drop as *not yet known*;
- test it once, gently, much later, from the machine that will fetch;
- count each unanswered test as evidence for a block, and so wait longer each time;
- hand it to a person after four.

That is what a block "costs days" asks for: the knocks are a day, two, four and seven days apart.

| Answer on the night, or to the knock | `classify()` today (`refusal.py:269-307`) | Whose it is under this design |
|---|---|---|
| `RemoteDisconnected`, reset, abort, `ConnectionRefusedError`, a timeout, `SSLEOFError` | dropped (two end a run) | **the night's to test** |
| the data page timing out | "slow", not counted (`snapshot_gencourt.py:257-262`) | unchanged: no refusal |
| HTTP **503** whose body is not the block page | refused (one ends the run) | **the night's to test**, never sooner than its `Retry-After` |
| 503 with a `Retry-After` over 160 h | refused | a person's |
| 503 carrying the block page | refused | a person's |
| **403**, **429** (with or without `Retry-After`), `Retry-After` on any other status | refused | a person's, as today |
| the block page, at any status | refused | a person's, as today |
| a 3xx redirect *on the knock* (the knock follows none) | not reached | a person's |
| 404, 5xx other than 503, or a body that is not a data file, *on the knock* | missing / failed | a failed knock (next rung), never a lift |

### Why 503 may heal (a decision, argued; no 503 from gc.nh.gov has ever been recorded)

1. **A 503 is the server's own "not now".**
   - The site is ASP.NET. Its own error pages are what `refusal.BROKEN` matches ("Runtime Error|Server Error in|Service Unavailable", `refusal.py:266`).
   - *Guess:* IIS answers 503 when an application pool is stopped or recycling. That is a maintenance outage, the very case the owner asks about.
2. **The firewall's verdict has always been pictured as the block page or as drops, never as a bare 503.** A 503 that carries the block page stays a person's, so the body has to be read. `classify()` returns before reading the body of a 503 (`refusal.py:286-287`), so a new reader, `refusal.unavailable()`, does that.
3. **It adds no new kind of risk.** A 503 that is really a block gets the same at-most-four single requests as a drop that is really a block, and drops are block 1's own signature. If the drop rule is safe, the 503 rule is too. If it is not, neither is.
4. **`Retry-After` is honoured, and a long one is believed.** The knock waits for the later of the rung and the `Retry-After`. A `Retry-After` past the last rung (160 h) is "go away for a week", which is a block in all but name, so it is a person's.
5. **429 stays a person's.** It is a rate complaint aimed at us.

`classify()` itself does not change, so a 503 still ends the run at once and every `_every_fetcher_notes_refusal` case stays green (preflight 77970-77974). Only the record's `kind`, and who may lift it, change.

---

## 2. The rule: whose a refusal record is

`refusal.whose(d, k)` is one function, in `refusal.py`, used by every reader. `d` is `archive/refused.json`; `k` is `archive/knocks.json` when it is about `d`.

**A record is the night's to test only if all of these hold:**
1. `d["kind"]` is `"dropped"` or `"unavailable"`.
   - A record with no kind is a person's. That covers every record written before this change, today's 29 October record, all 55 `note()` call sites that pass no kind, and every fake record in preflight (81660, 82539, 89555, 89589, the lane's `'{}'`).
2. `d["machine"] == "github"`. It was written where `GITHUB_ACTIONS == "true"`.
   - Refusals met on the laptop are the address blocked twice, and they stay a person's.
   - This follows `probe_db`'s hold, which is "recorded on GitHub's machine only" (`probe_db.py:106-110`).
3. `d["dry"] is False`, written as such. A dry run is any run where `DRY_RUN == "true"` or `GITHUB_REF != "refs/heads/main"` (`nightly.py:596-620`).
   - A refusal's kind is written by the code that met it. Main's night must not trust a kind that unmerged code wrote.
4. `d.get("retry_after", 0) <= 160 * 3600`.
5. `k` names this record (`k["refusal"] == sha256 of refused.json's bytes`). Then:
   - `k["person"]` is unset;
   - fewer than `KNOCKS_MOST` = 4 knocks have been made.
   A `k` about another record is ignored.

**Anything else is a person's**, and every reader says so in the words it says it in today.

---

## 3. The knock

| | |
|---|---|
| **What** | `GET https://gc.nh.gov/dynamicdatadump/Counties.txt`. It was 195 bytes on 28 October (that night's log, line 1697). It is in the 14 the night asks every night (`snapshot_gencourt.py:104`, `:119`). It has no query string and no retry. |
| **Not** | the data page `dynamicdatadump/`, which "rebuilds every table before it answers" (`:217-232`); an invented path (block 1); a second host; netcheck |
| **Headers** | the snapshot's own User-Agent, `granite-record/1.0 (civic transparency archive; contact@graniterecord.org)` (`:124-125`). Netcheck sends a browser's in 7 of its 8 requests. |
| **Limits** | 60 s socket timeout (`KNOCK_TIMEOUT`). The child is killed at 2 min (`KNOCK_MINUTES`, `run(timeout=)`). **No redirect followed**: an opener without `HTTPRedirectHandler`, so a knock is exactly one request. |
| **From** | GitHub's runner, inside `nightly.py --runner`, under `refusal.hold("nightly")`, as the child `snapshot_gencourt.py --knock`. Never Cloudflare (the live Worker), a cloud container, or the laptop. |
| **When** | after preflight passed, before the export, in the night's fetch block. Only when all of these hold: `--runner`; not `--dry-run`; not `--new-term`; the record is the night's to test (§2) and due (§4); and `asking_left(KNOCK_MINUTES + EXPORT_MINUTES)` gives a deadline (§11). |

**Why from the runner, inside the job.** Only a request from the machine that is about to fetch can show that the fetch will be answered.
- A knock from Cloudflare, a cloud container or the laptop would prove nothing about the runner. Netcheck's 200s from a container on 29 October prove nothing about the runner either.
- It would also be a second machine asking beside the night, which is how the second block was earned (`snapshot_gencourt.py:20-27`, `refusal.py:312-316`).
- Under the night's lock and its `gc-night` job concurrency (`nightly.yml:246-248`), no other night or weekly job runs at the same time.
- 08:00-13:30 UTC is the window inside which a stood-down laptop starts no request, and before which it must pull (`refusal.py:520-533`, `:707-744`).

**Why `Counties.txt` and not `Members.txt`.**
- It is the smallest data table the night already asks for: 195 bytes against `Members.txt`'s 82,694.
- It is on the same path as the export that dropped.
- It is above `MIN_BYTES` (40, `:131`), so `read_one()` can tell a whole file from an error page.
- *Guess:* the downloads page says its tables "refresh on file access". If asking for this file rebuilds it, that rebuild is ten counties.

**What counts:**

| Answer | Result | Exit |
|---|---|---|
| 200, and `read_one()` returns data (at least 40 bytes, not HTML, not the block page) | **lifted** (§5) | 0 |
| 403, 429, the block page at any status, a 3xx, a 503 with the block page, or a `Retry-After` over 160 h | **a person's**: `k["person"]` gets the sentence, and nothing more is asked | 2 |
| dropped or timed out; a 503 without the block page; 404; another 5xx; a body that is not a data file; or killed at 2 min | **a failed knock**: the next rung, or a person's if this was the fourth | 1 |

**Crash-safe.**
- `refusal.knocking()` appends `{"answer": "no answer", ...}` to `knocks.json` *before* the request.
- `refusal.knocked()` then rewrites that entry with the answer.
- So a knock killed or crashed mid-request still counts as a knock, and the next one waits for the next rung. The ladder only ever lengthens on an unknown.

**"Stable" is one answered knock, then the night's own export.**
- After a lift, the snapshot asks its usual 15 requests under its usual stop-loss: two drops, or one refusal, end it.
- If that relapses (§5), the new record keeps the ladder, so a flapping server cannot win a fresh first rung.
- Two knocks a few minutes apart would double the requests to a server that may be blocking, and would prove less than the export does.

---

## 4. The schedule, and the ceiling

`KNOCK_HOURS = (16, 40, 88, 160)`.
- Each wait is counted from the **last request that failed**: the refusal itself, then the last knock.
- The knock waits for the later of that rung and any `Retry-After` (on the record, or on the last knock's 503).
- That is one night, two, four and seven, each eight hours short.
- `KNOCKS_MOST = 4`. After the fourth knock fails, the record is a person's.

**Why 16 and not 20 (`probe_db`'s first rung) or 24 (`QUIET_HOURS`).**
- **Not 24:** the 29 October record is at 08:27:15 UTC. The next timer night asks at about 08:23-08:27, which is the 08:17 start plus kit-down and about 6 min of preflight (read_night §2). That is 23.9-24.0 h later, so a 24 h rule would miss it, or catch it only by seconds.
- **Not 20:** 20 h is enough for a refusal met at 08:27. But GitHub's own cron ran nights 5-7 h late on 19-24 Oct, created as late as 15:38 UTC (read_holds rank 12), and the export is asked whenever a night runs (nc docstring, "The day's files keep their own rule"). A refusal at 15:38 plus 20 h is 11:38, so the next 08:27 night would not knock, and the site would lose a second day.
- **Why 16 works:**
  - 15:38 plus 16 h is 07:38, so the next morning knocks.
  - No refusal can be knocked in its own day's window: the earliest refusal, 08:00, plus 16 h is midnight.
  - The window gate keeps any knock out of the hours between.

**The 29 October record, as if it were the night's to test** (computed from epoch 1793262435):

| Knock | Due from (UTC) | Asked on the night of |
|---|---|---|
| 1 | 30 Oct 00:27 | 30 Oct, about 08:27 |
| 2 (if 1 failed at 08:27) | 1 Nov 00:27 | 1 Nov |
| 3 | 5 Nov 00:27 | 5 Nov |
| 4 | 12 Nov 00:27 | 12 Nov |
| then | a person's | — |

**The ceiling, and what enforces each part:**
- **At most one knock request a day.**
  - Knocks happen only between 08:00 and 12:00 UTC (`asking_left`, nc `nightly.py:3923-3962`).
  - The shortest rung (16 h) is longer than that 4-hour window, so no two knocks can share a window.
  - The night calls `knock()` at most once per run.
  - `gc-night` runs night jobs one at a time, so a hand run of main reads the state the previous run sent (§5).
- **At most four knock requests per outage**, counted across relapses within 168 h of a lift (`RELAPSE_HOURS`).
- **Each knock is exactly one GET:** no redirect, no retry, a 60 s socket timeout, and killed at 2 min.
- **What it never asks:** the data page, another host, another path, or anything from another machine.
- **After a lift the night makes its ordinary requests**: the page, 14 files and their single 60 s retries, then the clock-gated bill requests and lists. That is the same traffic as the 50 healthy passes since 30 September.

---

## 5. The lift, and the bucket

**One new state file: `archive/knocks.json`, R2 `state/knocks.json`.**
- `refusal.py` writes it. `refused.json` stays write-once, so every existing comparison by sha keeps working unchanged: `state_up` (`cloud.py:1627-1700`), `pull_refusal` (`2754-2860`), `send_refusal` (`2137-2207`) and `clear-refusal`'s `cleared` (`2108-2112`).

```json
{
 "refusal": "<sha256 of archive/refused.json as the bucket holds it>",
 "where": "snapshot_gencourt", "at": "2026-10-29T04:27:14",
 "knocks": [{"utc": "2026-10-30T08:27:40Z", "epoch": 1793349060.0, "run_id": "…",
             "url": "https://gc.nh.gov/dynamicdatadump/Counties.txt",
             "answer": "whole", "said": "a whole Counties.txt, 195 bytes"}],
 "person": null,
 "lifted": {"utc": "…", "epoch": 0, "run_id": "…", "by": "the night's knock",
            "record": {"at": "…", "epoch": 0, "where": "…", "why": "…", "kind": "dropped", "…": "…"}},
 "carried_from": null
}
```

**The lift, on GitHub's machine.** `refusal.knocked(None, …)` does this:
1. writes `lifted`, with the whole refusal record inside it. `refusal` is the sha of the bytes read **before** tonight's knock. Those are the bytes `state-down` brought down, so they match the bucket's;
2. only then removes `archive/refused.json`.

The record is therefore moved into `knocks.json`, not lost. This follows the "moved, never deleted" that `_cloud_state_and_site` holds (55341-55344).

**The lift, in the bucket.** `cloud.lift_refusal(bucket, root, kit, rep, day)` is called at the top of `state_up`.
- **It acts only when all hold:**
  - `only is None` (not a dry night);
  - `GITHUB_ACTIONS == "true"`;
  - `GITHUB_REF == "refs/heads/main"`;
  - `DRY_RUN != "true"`;
  - the local `knocks.json` has `lifted`;
  - its `refusal` equals the sha of the bucket's `state/refused.json`.
- **What it does:** it moves that object to `replaced/<day>/`, as `clear-refusal` does (`Replacer.keep`, then `delete`; `cloud.py:2104-2105`), and records the sha as `cleared` in this machine's state record.
- **Then:** `state_up`'s loop sends `knocks.json` as any changed state file.
- **No workflow change is needed.** The final state-up runs `always()` (`nightly.yml:534-543`), and "A refusal goes to R2 at once" (`449-459`) runs it too when a new refusal is on file.
- **The lift reaches the bucket after `nightly.py` exits, before 13:30 UTC.** The laptop is held until then, and must pull afterwards (`refusal.py:520-533`, `730-743`).
- **If the job dies before state-up:** the bucket keeps the refusal, and the next night knocks again. One knock on one more night is the safe direction.

**The laptop reads the lift from the bucket.** A "cleared" kept only on the machine that cleared it would leave a trap (read_refusal §3):
- **`pull_refusal`** reads `state/knocks.json`. A laptop copy whose sha is the bucket's `lifted.refusal` is reported as a line, not as the "IS NOT IN THE BUCKET" failure (`cloud.py:2801-2807`): "the night lifted this refusal on <date>: <said>. It is still on file here, and the lane here stops at it until python3 refusal.py --clear."
- **`send_refusal`** never sends that sha back (beside `cleared`, `cloud.py:2168-2174`).
- **The laptop's own copy and its lane stay a person's** (`gc_lane.py:402-406`). The laptop is attended, and its share of the record is already a person's to start (read_holds rank 8).

**Relapse.** `refusal.note()` on GitHub's machine checks for a `knocks.json` that was `lifted` less than `RELAPSE_HOURS` = 168 h ago.
- If there is one, the new record's `knocks.json` starts with the old one's knocks (the answered one included), plus `carried_from`.
- So the next wait is the next rung, and the fourth knock in a week ends it.
- A refusal that is a person's ignores this.

**Dry runs never lift:**
- the night never knocks on `--dry-run`, which the ref sets too (`nightly.py:1443-1450`);
- `note()` marks a dry run's record `dry: true`, so it is never the night's to test;
- `knocks.json` joins `DRY_NEVER` (`cloud.py:457`), so a dry night never sends it;
- `lift_refusal` never runs with `only`.

---

## 6. What stays a person's, for good

- 403, 429, `Retry-After` on anything but a 503, and the firewall's block page, met on the night (unchanged).
- Any of those answered to a knock, a 3xx to a knock, or a `Retry-After` over 160 h.
- A fourth knock unanswered, counted across a relapse within a week.
- Every refusal met on the laptop, and the laptop's own copy and lane (`refusal.py --clear` there).
- Every refusal met by a dry run, and every refusal recorded before this change, **the standing 29 October record included**.
- Every refusal noted by a fetcher that passes no kind: everything but `snapshot_gencourt` and `fetch_committees`. That includes `fetch_lsrs` and the listing on the night, which in any case exit on one drop without a record (`fetch_lsrs.py:117-120`, `fetch_calendar_archive.py:612-616`).
- Clearing any refusal sooner (`netcheck.py`, `cloud.py clear-refusal`, `refusal.py --clear`), and reading what netcheck printed.
- Writing to the Clerk's office about a block.
- Unchanged, outside this design:
  - using the database while a web refusal stands (§12);
  - approving a night the gate holds;
  - the new term;
  - the YouTube key and the Cloudflare token.

---

## 7. The alert

**Healthchecks keeps its behaviour.**
- A night with a refusal on file is not clean, so the night's check gets `/fail` with `logs/alert.txt` as the body (`nightly.yml:585-596`).
- Healthchecks emails once when the check goes down and once when it comes back (`nightly.py:5685-5690`). What changes is what the email says.

**1. The night a refusal is met.** This is the down email, and the line is `alerts_of()`'s:
> The General Court's site closed two connections without answering at 08:27 UTC on 29 October (snapshot_gencourt). Nothing more was asked. This kind is tested by the night itself: one request for Counties.txt, a 195-byte file it asks for every night, on the night of 30 October; if that comes back whole the night carries on as usual and this check comes back up. If it does not, it tries once more on 1, 5 and 12 November, and then waits for you. Nothing is needed from you; to lift it sooner: python3 netcheck.py, then python3 src/ops/cloud.py clear-refusal.

- The dates are `refusal.knock_schedule(d, k)`: every date on which a knock may come, if each knock fails.
- So the first email tells the person when to expect the up email, and silence after that date means the knock failed.

**2. A night that waits or knocks in vain.** Still `/fail`, so there is no new email. The body and the run's page say: "… the knock at 08:27 UTC was not answered (closed without a byte); the next is on the night of 1 November."

**3. A lift.**
- The verdict gets `"knock": "lifted: Counties.txt came back whole (195 bytes) at 08:27 UTC; the refusal of 29 October is moved to state/knocks.json"`, and the log gets the same line.
- If the night is clean, the end ping is a success, and Healthchecks' up email is the person's news.
- **This is not a warning kind.** A new kind would hold the night for approval (`warning_reasons`, read_holds §3.2), which would defeat the lift.

**4. It becomes a person's** (a block-type answer to the knock, or the fourth knock failing).
- `alerts_of()` uses today's person's sentence, prefixed with why: "the knock at 08:27 UTC on 1 November was answered by the firewall's block page; it is a person's to clear now".
- **The same line also goes to `warns_of()`**, so the warnings' check (`HEALTHCHECKS_WARN_URL`, `nightly.yml:597-616`) emails it if that check was up.
- **The gap, said plainly:** the night's check has been down since the refusal, so it sends no new email at escalation. If the warnings' check is also already down, there is no email at all. *Guess:* read_night thought it was probably down already for the captions inbox. The schedule in email 1, the dashboard and the run's page still say it.
- An optional fourth check closes the gap (§15, decision 6).

---

## 8. The changes, file by file

**`refusal.py`** (`2026-09-09.19` becomes `.20`)
- **New constants:**
  - `KIND_RESUMABLE = ("dropped", "unavailable")`;
  - `KNOCK_HOURS = (16, 40, 88, 160)`;
  - `KNOCKS_MOST = 4`;
  - `RELAPSE_HOURS = 168`;
  - `RETRY_AFTER_MOST = 160 * 3600`;
  - `KNOCKS = Path("archive/knocks.json")`.
- **`note(where, why, kind=None, retry_after=None)`** (`:113-127`):
  - adds `kind`, `machine` (`"github"` if `GITHUB_ACTIONS == "true"`, else `"laptop"`), `dry`, `run_id` and, when given, `retry_after`;
  - carries the ladder on a relapse (§5);
  - leaves `tell_the_bucket` unchanged.
- **`unavailable(err)`:** for an `HTTPError` 503 whose body (first 4,000 bytes) does not match `BLOCKED`, the `Retry-After` in seconds (0 when absent or unreadable; seconds or an HTTP date); `None` otherwise.
- **New readers of the record:**
  - `whose(d, k)` returns `("knock" | "person", why)` (§2);
  - `knock_due(d, k, now=None)` returns `(bool, due_epoch)` (§4);
  - `knock_schedule(d, k)`.
- **`check(who="", knock=False)`** (`:223-252`): with `knock=True`, it exits 2, asking nothing, unless all of these hold:
  - this is GitHub's machine;
  - the run is not dry;
  - `MARK` exists;
  - `whose()` is `"knock"`;
  - `knock_due()` is true.
  It reads `MARK` at any age, not through `standing()`. Without `knock`, it is unchanged.
- **The knock's writers:**
  - `knocking(url)` records the attempt before the request;
  - `knocked(answer, said)` records the answer, and on a whole file lifts (§5).
  Both write a part file, then rename it.
- **`force()`** (`:195-208`) and **`main()`'s status** (`:861-867`) say whose the record is and when the next knock is due.
  - This also fixes "older than 24h and no longer stops anything", which is false for the night and the lane.
- **Docstring:** "HOW IT BEHAVES" (`:30-38`) gets a paragraph, "THE NIGHT'S KNOCK (… 2026, the person's decision)", stating §2-§5.
  - "Nothing clears it automatically" becomes: "Nothing clears a person's refusal automatically; the one exception is §… and it is one request a day at most."

**`src/fetch/gc_web/snapshot_gencourt.py`** (`2026-09-04.13` becomes `.14`)
- **New constants:** `KNOCK_NAME = "Counties.txt"`, `KNOCK_TIMEOUT = 60`, and a no-redirect opener for the knock.
- **`read_one(url, name=None, timeout=120)`:**
  - its error is `(kind, why, retry_after)`;
  - a 503 that `refusal.unavailable()` accepts is kind `"unavailable"`.
- **`open_page()`:** the same for the page.
- **`run()`:**
  - stops at once on `"unavailable"` as on `"refused"`;
  - passes `kind=` (`"refused"`, `"unavailable"` or `"dropped"`) and `retry_after=` to `note()` at its three sites (`:585`, `:615`, `:621`);
  - the drop counting (`:587-588`, `:618-630`) is unchanged.
- **`main()`:**
  - adds `--knock`, after `--plan` and `stand_down()`, as its own branch;
  - the branch calls `refusal.check("The knock", knock=True)`, then `with refusal.hold("the knock") as held: return knock(held)`;
  - the normal path still calls `refusal.check("The daily snapshot")` (`:517`).
- **`knock(held)`:** `still()`, `knocking()`, one request, the judgement in §3, `knocked()`. It returns 0, 1 or 2.
- **`:683`:** "holds every fetch for a day" becomes "holds every fetch: a person's to clear, or the night's knock's (refusal.py says which)".

**`nightly.py`** (on top of night-clock's `2026-09-04.80`)
- **New constants:** `KNOCK_MINUTES = 2` and `EXPORT_MINUTES = 36`.
  - The 36 is computed, not measured: the page's 300 s, 14 files × 120 s, 14 pauses of up to 5 s, and one 60 s retry, which is 2,110 s.
- **`knock(a, night)`, the one place the night knocks:**
  - it returns `(lifted, why)` and sets `night.v["knock"]`;
  - it is gated by `asking_left(KNOCK_MINUTES + EXPORT_MINUTES)`;
  - it runs `run(["snapshot_gencourt.py", "--knock"], "one knock on the General Court's site", timeout=min(KNOCK_MINUTES * 60, seconds_left(deadline)))` inside its own `with refusal.hold("nightly")`, before the export's block.
- **The fetch block** (`:1541`; nc `:1616`):

  ```python
  ok, why = gc_quiet()
  if not ok and a.runner and not a.dry_run and not a.new_term and refusal.MARK.exists():
      lifted, said = knock(a, night)
      ok, why = gc_quiet() if lifted else (False, said or why)
  ```

  The rest is unchanged. A failed or skipped knock is "FETCH DEFERRED", as today.
- **`gc_quiet()`** (`:1233-1246`): its sentence names whose the record is and, for the night's, when the knock is due. It still returns False for any record.
- **`alerts_of()`** (`:5758-5763`), **`warns_of()`** (`:5739-5747`, the escalation line) and **`plain_why()`** (`:2283-2285`, `:2317-2318`) get the §7 sentences.
- **"REFUSED while fetching"** (`:1704-1706`) and **the docstring at `:26-30`** become: "a refusal on file, at any age, means no fetch tonight, unless it is one the night tests itself (THE NIGHT'S KNOCK), and then one request first".
- **THE NIGHT'S CLOCK paragraph** (nc `:447-468`) names the knock as a third gated step.

**`src/fetch/gc_web/fetch_committees.py`:** `note(..., kind=kind)` at its two sites (`:235`, and the block page at `:241`). Without it, a Monday weekly that met two drops would stop every night until a person acted, which is this incident again.

**`src/ops/cloud.py`** (`2026-09-25.26` becomes `.27`)
- adds `lift_refusal()`, called first in `state_up()` (§5);
- `pull_refusal()` and `send_refusal()` read `state/knocks.json`;
- `DRY_NEVER` gets `"knocks.json"`;
- `state_up`'s docstring adds: "or by the night's own knock, which leaves state/knocks.json naming the refusal it lifted".

**`cloud_kit.json`**
- a state entry for `archive/knocks.json`;
- the `refused.json` "what" becomes: "A refusal on file: nothing asks the General Court, from either machine, until a person clears it, or, for one the night tests itself, until one request the night makes is answered (refusal.py, THE NIGHT'S KNOCK)."

**Unchanged**
- `classify()` and the drop counting;
- `gc_lane.py`;
- `from_database` and the five database gates;
- `nightly.yml` and `weekly.yml`;
- `netcheck.py`;
- `probe_db.py`;
- the night-timer.

**`versions.json`:** every changed file's stamp, by `python3 src/ops/inventory.py --bump-changed`.

---

## 9. The checks, each of which fails if its rule is removed

All of them use fakes, with no network, in the patterns `_snapshot_stops` and `_nightly_runner` already use. Each runs under `preflight --code`.

### `_refusal_kinds` (new, `refusal.py` alone)

| Fixture | Expected | Fails if |
|---|---|---|
| `note(..., kind="dropped")` with `GITHUB_ACTIONS=true` and `GITHUB_REF=refs/heads/main` | `whose() == "knock"` | the kind is not written |
| the same with no `GITHUB_ACTIONS` | `"person"` | the machine rule is gone |
| the same with `DRY_RUN=true` | `"person"` | the dry rule is gone |
| the same with ref `refs/heads/dev` | `"person"` | |
| the 29 October record's exact bytes (`{at, epoch, where, why}`) | `"person"` | a kindless record becomes resumable |
| kind `"refused"` | `"person"` | |
| `"unavailable"` with `retry_after` 3,600 | `"knock"` | |
| `"unavailable"` with 161 h | `"person"` | `RETRY_AFTER_MOST` is gone |

**Due times:**
- with epoch 1793262435 and `GRANITE_CLOCK_UTC=2026-10-30T08:23:00Z`, `knock_due` is True. This fails if the first rung is 24 h or more;
- at E + 15.9 h it is False. This fails if the first rung is under 16 h;
- after knocks failing at K1, K2 and K3, it is due at exactly +40, +88 and +160 h;
- after four knocks, `whose()` is `"person"`;
- a 503 knock with `Retry-After` 50 h pushes the due time past +40 h.

**Constants and the 503 reader:**
- `min(KNOCK_HOURS) > 4`, where 4 h is the night window's 08:00 to `ASK_UNTIL`. This fails if a rung could allow two knocks in one window;
- `unavailable()` gives `None` for a 503 carrying `_BLOCK_PAGE`, `None` for 429 and 403, and seconds for an HTTP-date `Retry-After`.

### `_the_knock` (new, `snapshot_gencourt.py --knock` through `main()` on a faked `urllib.request` opener)

**What it asserts about the one request:**
- exactly one opener call, to `BASE + "Counties.txt"`, with the snapshot's `UA` and never `PAGE`. This fails if the knock asks twice, asks the page or sends a browser User-Agent;
- the opener has no redirect handler.

**Each answer, and what it must leave:**

| Answer | Exit and state | Fails if |
|---|---|---|
| 195 bytes of data | exit 0; `MARK` gone; `knocks.json["lifted"]["record"]` equals the old record; `refusal` equals the sha of the pre-knock bytes | deleted without keeping, or the sha is taken after the knock |
| the block page as 200 | exit 2; `person` set; `MARK` still there | the block page counts as answered |
| 403, 429, 429 with `Retry-After`, a 302, or a 503 carrying the block page | `person`, each one | |
| a 503 without the block page, `RemoteDisconnected`, a timeout, a 404, or `<html>` with 200 | exit 1; a knock counted; still `"knock"`; due 40 h later | |
| the opener raising `SystemExit` after `knocking()` | a "no answer" entry stands | the attempt is written only after the answer |

**When it must ask nothing at all** (exit 2 and **zero** opener calls):
- a record 2 h old. This fails if `check(knock=True)` is removed;
- a kindless record;
- `DRY_RUN=true`;
- no `GITHUB_ACTIONS`.

**AST:** the `--knock` branch of `main()` calls `refusal.check(…, knock=True)` before `knock()`.

### `_nightly_knocks` (new, `nightly.py --runner` on fakes, as `_nightly_runner` does)

| Fixture | Expected | Fails if |
|---|---|---|
| a resumable record that is due, clock 08:30 UTC | `snapshot_gencourt.py --knock` once, then the normal snapshot; fetch installed; `v["knock"]` starts with "lifted" | the night never knocks, or knocks twice |
| the same at 11:30 UTC (11:30 + 38 min is past 12:00) | no call; "not asked for"; deferred | the clock gate is gone |
| the same at 14:33 UTC | no call | |
| a record that is not due | no call; the why names the due time | |
| the kindless record of `_nightly_runner` 108 (82537-82547), kept as it is | no call, so "asked the General Court with a refusal on file" still holds | |
| `--dry-run` or `--new-term` | no call | |
| knock rc 1 | deferred; no normal snapshot call; one knock only | |

`warning_reasons()` on a lifted night's warnings gives no reason from the knock. This fails if the lift becomes a warning kind that would hold the night.

### `_cloud_lift` (new, folder bucket, as in `_cloud_state_and_site`)

| Fixture | Expected | Fails if |
|---|---|---|
| bucket holds R; local `knocks.json` lifted for sha(R); `GITHUB_ACTIONS` set; main | `state_up` puts R under `replaced/<day>/`; `state/refused.json` is gone; `state/knocks.json` is sent | it deletes without moving, or never lifts |
| lifted sha ≠ the bucket's | nothing moved | |
| `only=` (a dry night) | nothing moved; `knocks.json` not sent | `DRY_NEVER` loses it |
| no `GITHUB_ACTIONS` | nothing moved | |
| a local refusal absent and no `knocks.json` | nothing removed | the existing "absent here is never removed there" is broken |
| a relapse (a new local refusal plus a lift for the old one) | old moved, new sent | |

### Changed checks

- **`_cloud_pull`** (58726): a laptop copy under 24 h old that the bucket lacks, with the bucket's `knocks.json` lifted for its sha, gives a line, not a failure, and `send_refusal` returns done without sending. This fails if pull ignores the bucket's lift.
- **`_snapshot_stops`** (81515): the incident's sequence (page dropped, then a file dropped) writes `kind: "dropped"`; a 403 writes `"refused"`; a 503 carrying the block page writes `"refused"`; a bare 503 writes `"unavailable"`, and the run stops at once.
- **`_alarm_stays_able_to_ring`** (109839):
  - a resumable record's alert names the next knock date and says "Nothing is needed";
  - a person's names `clear-refusal`;
  - an escalated one is in `warns_of()` too.
- **`_night_clock`** (nc 92277): `gated == ["knock", "take_documents", "take_lsrs"]` (nc 92374), and the docstring sentence becomes "those three steps".
- **`_assistant_guard`** (67182): if decision 7 is taken, add the table rows (§15).
- **Left as they are, and must stay green:**
  - `_nightly_guards` (81660: an old kindless record defers);
  - `_nightly_falls_back` (90012-90130: this design leaves the database gates alone);
  - `_every_fetcher_checks_refusal`: the knock lives in `snapshot_gencourt.py`, which already calls `check()`, so no new script and no exemption;
  - `_every_fetcher_notes_refusal` (`classify()` unchanged);
  - `_lane_daily`;
  - `_night_window`.

---

## 10. Documents, and the CLAUDE.md wording

**Each changes in the same commit as the code:**

| Document | Lines |
|---|---|
| `README.md` | 344-353 |
| `ARCHITECTURE.md` | 113-117, and 266-272 ("its recovery is the sign it was cleared" becomes "… that it passed, by the night's knock, or was cleared") |
| `CONTRIBUTING.md` | 24-31 |
| `SECURITY.md` | 93-98 |
| `watchers/README.md` | 71-83 (the lift's line at pull) |
| `cloud_kit.json` | the two "what"s |
| docstrings | `refusal.py`, `nightly.py`, `snapshot_gencourt.py:683` |

**CLAUDE.md is the owner's to edit.** Proposed replacement for lines 74-79:

> **A refusal outlives the run that met it.** `refusal.py` records one in
> `archive/refused.json`, with what kind it was. It exists because a drain that
> met two 403s stopped itself correctly, and a chained run started asking the
> same address for a docket fifty-four seconds later. A fetch started by hand
> here waits 24 hours; the lane and GitHub's night wait for as long as it is on
> file. One kind is the night's to test, by the person's decision of
> <date>: dropped connections, timeouts or a 503 that is not the firewall's
> page, met by GitHub's night. The night asks once for `Counties.txt` from
> inside its own job, between 08:00 and 12:00 UTC, on the next night and then
> after two, four and seven more nights; a whole file lifts it, moved into
> `archive/knocks.json`, and the night goes on. Everything else -- a 403, a
> 429, the firewall's page, any such answer to that request, a fourth request
> unanswered, any refusal met on this laptop or by a dry run -- is a person's to
> clear, as it always was: `python3 refusal.py --clear` here and
> `python3 src/ops/cloud.py clear-refusal` for the night's, after `netcheck.py`
> has said what kind of refusal it was.

This also corrects two existing mistakes in CLAUDE.md:
- **"twelve seconds"**: `refusal.py:22-24` and HANDOFF at 4bbe30d say fifty-four;
- **the lane "for 24 hours"**: it holds at any age (`gc_lane.py:402-406`).

---

## 11. With the night's clock (`feat/night-clock`)

**It reuses:**
- `asking_left(minutes)` (nc `:3923-3962`), which allows a step only inside the daily window and only if it ends before `ASK_UNTIL` = 12:00 UTC;
- `seconds_left()` (nc `:3964`);
- `run(timeout=)`, which kills a child at its limit and gives `RUN_KILLED = 124` (nc `:1192`).

**The gate's minutes are `KNOCK_MINUTES + EXPORT_MINUTES` = 38, not 2.**
- A lift opens straight onto the export, which the clock deliberately leaves ungated (nc docstring "The day's files keep their own rule").
- With 38 minutes, the knock *and* the export it may lead to both end before 12:00.
- So a refusal the relapsed export records still reaches the bucket well before 13:30. That is the clock's own reason for 12:00 (nc `:711-717`).
- The child is killed at `min(120 s, seconds_left(deadline))`.
- A late night (GitHub's cron, 14:33-15:38) gets "not asked for" and waits a day, as the bill requests do. The record stands, so nothing else asks either.
- The clock's "not asked for" never holds the gate (nc `clock_kind`). Here there is nothing to publish anyway.

**What has to change in the clock's check:** `_night_clock` pins the gated callers to exactly `["take_documents", "take_lsrs"]` (nc `preflight.py:92374`), and the docstring says "those two steps". Both change to three. So this lands after the clock merges, as one commit on top of it.

---

## 12. The owner's idea, weighed

> "the live updates may assist ... the nightly can resume whenever the live shows it's up again"

**Where it cannot help: it cannot show that the web server is back.**
- The live Worker reads PublicSQL and YouTube and "never gc.nh.gov" (design_final.md §0).
- A healthy database proves little about a web server that dropped.
- Any test it made would come from Cloudflare's addresses, not the runner's. It would also be a second machine asking beside the night.
- On 29 October it would not have read at all. Outside January-June, with no sitting, it is Off (§2.3), and its heartbeat never starts inside the window.
- It writes its own bucket, which the night holds no credentials for (`nightly.yml:334-337`).

So the knock in this design is the "single, spaced knock on the web server" the manager described, made by the one machine that can prove anything.

**Where it does help, and how this design leaves room for it:**
1. **The database as the night's source while a refusal the night tests stands.** This is the larger win, and the owner's idea points straight at it.
   - PublicSQL answered whole on all 7 October fallbacks (read_history §2b).
   - The IT office: "No problem hitting PublicSQL during a session as it doesn't touch the website".
   - `probe_db.py:109-110` already says a web refusal does not hold that host.
   - With `whose()` in place, one narrow change would keep the site fresh *on the refusal day itself*, without one more request to gc.nh.gov. It would apply only while the record is the night's to test, never a person's. It would let three gates read `whose() == "knock"` instead of "a refusal is on file": `from_database` (`nightly.py:3011-3015`), the loop's "only after empty" (`1587-1589`), and `gc_quiet`'s coverage of the database steps (`1541`, `1626-1650`; the weekly's `5981`).
   - It reverses checks the person approved (`_nightly_falls_back` 90012-90024, 90112-90130), so it is the owner's decision, not part of the minimal change (§15, decision 9).
   - The `whose()` it needs is built here, so it would be a small follow-up.
2. **From January to June,** the Worker's heartbeat is an independent sign that the General Court's database is up. That is weak evidence for "outage, not block", useful to a person deciding whether to clear a refusal by hand. The night does not read it.
3. **During a sitting,** Live Now and the live votes keep the visible part of the site current while the night waits for its knock.
4. **Its holds already work this way** (design_final.md §2.6): expiring, never a person's, for the database. The knock carries the same idea to the web server, more cautiously.

---

## 13. Left out on purpose

- **A second knock later the same morning.** It would mean a job idling up to 3½ h, a time limit for the export (it has none: `nightly.py:1575-1578`), and a second pass through the try loop. It would recover outages under about 3 h on the same day; the 11 September one was under 61 min. It is also the "wait a bit and try again" from the very address that met the drop. Worth considering once this rule has met a real outage.
- **Letting the page's drop not count, so `Docket.txt` gets its one retry** (`snapshot_gencourt.py:587-588`, `:624-630`). That would add a request to a run already being dropped, with no evidence that it would have helped. With the knock, the strict rule costs one day, not an indefinite stop.
- **A new knock script, or netcheck as the knock.** A new script would need its own exemption in `_every_fetcher_checks_refusal`. Netcheck is unsuitable: 8 requests to two hosts, browser User-Agents, plain HTTP, and a verdict that counts a 403 as passing (`netcheck.py:92`, `:114`, `:162`).
- **The weekly knocking.** Its window is not the night's (`asking_left` reads only the daily window), and the night knocks the same day anyway.
- **Building and publishing main's code on a refusal night** (read_night §5d), and the database fallback (§12): separate decisions.

---

## 14. Risks

1. **A true block that looks like drops gets up to four single requests over 14 days.**
   - Bounded: each is 1 GET of 195 bytes, with our own User-Agent, at least 16 h apart.
   - The recorded blocks came from about 1,000 guessed URLs and from two workers at once.
   - *Guess:* whether a firewall's ban timer restarts on contact is unknown. Four requests in two weeks is the most such a timer would see.
2. **The knock cannot tell "the block ended" from "tonight's runner has another address".**
   - *Guess:* GitHub's hosted runners change address. The repository records none.
   - A lift may come from a fresh address. The night then asks its ordinary, polite, once-a-day traffic, which is not walking around a block in any sense that adds load. But it is a reason to keep the 403, 429 and block-page cases a person's, and they are.
3. **Flapping:** the knock is answered but the export drops. This is bounded by the carried ladder: at most 4 cycles in a week, then a person's.
4. **The gate may still hold the first night back** (read_holds §3.2):
   - the release proof lapses after 48 h;
   - more than 600 rows changed in session;
   - a new warning kind.
   The lift restores fetching, not necessarily publishing. The lift adds no warning kind of its own (checked).
5. **The escalation email gap.** The night's check is already down, and the warnings' check may be too (§7). The person learns of it from the schedule in the first email, the dashboard and the run's page, unless decision 6 is taken.
6. **The knock depends on the timer starting the night in the morning.** If the timer's token lapses and GitHub's cron runs nights late again (rank 12 in read_holds), knocks are "not asked for" every night. The refusal then stands until a person acts, which is today's behaviour, not worse.
7. **`Counties.txt` could be renamed or removed.** Knocks then fail as 404 and the record becomes a person's after four. The alert quotes the 404.
8. **The laptop's lane stays stopped** after a night lifts, until `refusal.py --clear` there. This is by design (an attended machine), but it is one more thing a person does.
9. **A sha mismatch at lift.** If the bucket's record changed between state-down and state-up, nothing is moved. The only way is a person's `clear-refusal` mid-night, which has then done it already. This is the safe direction.
10. **The design rests on reasoning from one drop event** (29 October) and three outages. None of them was a firewall block. The rungs are copied from `probe_db`'s tested shape, moved 4 h earlier for late nights, and have not been measured against gc.nh.gov.

---

## 15. For the owner to decide

1. **The rule itself.** A refusal met by GitHub's night as dropped connections, timeouts or a 503 that is not the block page may be lifted by the night's own single knock. This changes `refusal.py`'s "Nothing clears it automatically", `nightly.py`'s "at any age" and CLAUDE.md's paragraph. It needs the owner's OK, by their standing rule.
2. **503:** resumable, as argued in §1, or kept a person's (drop the "unavailable" kind; everything else stands).
3. **The knock's target:** `Counties.txt`, or `GeneralCodes.txt` (186 bytes), or another of the 14.
4. **The ladder and the cap:** 16/40/88/160 h and four knocks, then a person's. Or keep knocking weekly forever, as `probe_db` does.
5. **Clear today's record by hand.** It has no kind, so this design does not lift it.
6. **The escalation email:** accept the gap in §7, or add `HEALTHCHECKS_PERSON_URL`. That is one secret and a few lines in the ping step: `/fail` only while a refusal is a person's, a plain ping otherwise, so it emails exactly when one becomes the owner's.
7. **The assistant guard** (`.claude/hooks/guard.py:302-306`): ask before `cloud.py clear-refusal` and `send-refusal`. It asks before `refusal.py --clear` but not before the command that actually frees the night. Optionally ask before `netcheck.py` too, which makes 8 requests.
8. **Netcheck's verdict:** count only a 2xx without the block page as "got through", so that a person reading its last line is not told a 403 passed.
9. **Later, separately:** the database as the night's source while a refusal the night tests stands (§12). That is where the owner's idea keeps the site fresh on the refusal day itself.

---

## 16. Notes on the readers' findings

- **A dry run cannot overlap a main night's job.** read_refusal says a dry run by hand can overlap a main night (nightly.yml:143-145). That is the workflow-level group. The night *job* has its own `concurrency: group: gc-night, cancel-in-progress: false` (`nightly.yml:246-248`), shared with the weekly (`weekly.yml:102`), so two night jobs never run at once. That is what lets "one knock per run, at least 16 h apart" bound the knocks per day.
- **The night-clock tip moved.** It was 84a81ee in the brief. It is now 22d19e4 (f48edfe: "past 12:00 inside the window says outside the hours", then a merge of dev and stamps). `asking_left`, `seconds_left` and `run(timeout=)` are as the readers describe.
- **Effort, a guess:** about two working days.
  - **Day 1:** the code in six files and the four new checks.
  - **Day 2:** the changed checks, the docs, a full `preflight`, and one dry run to show a dry run neither knocks nor lifts.
  - The rule itself can only be exercised by a real refusal. The preflight fakes are its proof, and nothing should provoke one to test it.
