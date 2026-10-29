# The night that heals itself: addendum for the hourly knock

29 October 2026. Read-only design work. It amends `design_final.md` for the one change the owner made when approving D1–D6: knock **hourly**, not at 16/40/88/160 h. A builder follows `design_final.md` plus this addendum. Where they differ, this addendum wins. Sections not named here stand as written.

**Revised the same day after the safety red team** (§14 says, finding by finding, what was checked, what changed, and the three points corrected). The changes in short: hourly knocks only for a record that reached the bucket before the last window closed (§4.2); the laptop's `--clear` makes its next fetch pull first, and netcheck refuses beside a test (§7); no re-run reaches `gc-night` (§3.1); a claim the child does not use is marked "not asked" (§1.6); the look job reads with a read-only R2 key and both jobs install hash-pinned packages (§3); the night says once, by email, when the hourly knock has stopped (§6.1); knock dry runs wait in a group of their own (§3.2).

**Code read.**
- `origin/dev` = `4590795` when this was written; it has since moved to `db56680`, one commit touching only `corrections/README.md` and `corrections/rollcall_corrections.json`, none of the files cited here.
- `origin/feat/night-clock` = `22d19e4`. `.github/workflows/`, `refusal.py`, `src/ops/cloud.py` and `cloud_kit.json` are byte-identical on both (`git diff --stat` is empty for them), so their line numbers hold on either branch. Lines marked **nc** are night-clock's `nightly.py` and `preflight.py`.
- The repository's default branch is `main` (`git ls-remote --symref origin HEAD`). So a scheduled `knock.yml` runs only from `main`'s copy.

**Evidence made for this.**
- `hourly_ladder_sim.py` and `hourly_ladder_jitter.py` in this folder simulate the ladder below, with every knock failing. They mirror `refusal.NIGHT_WINDOWS` and `START_MARGIN_MINUTES` (`refusal.py:520-533`). They ask nothing of anyone.
- `hourly_ladder_late.py` adds the red team's two clock rules (the settle rule of §4.2 and the claim's slack of §1.6) and tries every five-minute start in a week.
- Every count in §2 comes from them.

**"Guess"** marks what neither the code nor a measurement shows.

---

## 0. What changes, on one page

| design_final | Becomes |
|---|---|
| §2.5 `KNOCK_HOURS (16, 40, 88, 160)`, `KNOCKS_MOST 4`, `HELD_MOST_HOURS 384` | **Three settings**, as repository variables: `KNOCK_HOURLY_HOURS` (48), `KNOCK_EVERY_HOURS` (6) and `KNOCK_DAYS` (16). There is one rung per hour for the first 48 h after the record's start, then one per 6-hour rung, until day 16. `KNOCKS_MOST` is gone (§1.5) |
| One knock a day, from the night only | **Two callers, one ladder, one state file.** The night still knocks once at its start, 08:00–11:18 UTC. A new workflow, `.github/workflows/knock.yml`, knocks at :47 past each hour, **outside** 07:30–13:30 UTC and Monday 03:30–06:30 UTC. Neither knocks twice in one rung (§1, §4) |
| §0 "New scripts, machines: none" | **One new workflow**, `knock.yml`, on GitHub's runners. The knock job runs on the night's own image, `windows-2022`. No new script and no new machine outside GitHub. **Two new secrets beside D5's:** a read-only R2 key for the look job (§3.2, §6.2). **One new tracked file:** `requirements-r2.txt`, boto3 and its dependencies with hashes (§3.2) |
| (new) the laptop and GitHub asking at once | **An hourly knock only for a record noted at least `KNOCK_SETTLE_MINUTES` (60) before the last window closed** (§4.2), so every laptop that may ask has pulled it. A late night's record waits for the next morning's night knock. On a stood-down laptop, `refusal.py --clear` makes the next fetch pull first, and netcheck refuses while GitHub may be testing the copy it holds (§7) |
| §0 "at most 1 a UTC day, at most 4 per outage" | **At most 19 a UTC day for the first 48 h, then 4 a day. At most 94 knocks per outage, so 96 single requests with day 0's two.** The plain arithmetic, 48 + 56 = 104, is the same count without the night's quiet hours (§2) |
| §2.4 "exit 2 and asks nothing" for a gate refusal | **Exit 4** ("not asked", the stand-down's status). 2 stays "a person's" only. The hourly workflow would otherwise email "a refusal is yours" when the window simply opened (§4.3) |
| §2.4 write-first in `knocks.json` | Plus, for the hourly caller, **the claim reaches the bucket before the request**. An answer the bucket never heard is a person's. A claim the child did not use is marked "not asked" before the state goes back (§1.6) |
| §2.7 relapse bounded by `KNOCKS_MOST` | `RELAPSES_MOST = 4`: the fourth relapse in a chain makes the record a person's. This keeps the approved flapping bound (§1.5) |
| §2.9 the third check pinged by the night | Also pinged **`/fail` only** by `knock.yml`, the moment a record it was testing becomes a person's (§6). The night also raises one alarm, through its own check, the first morning it finds the hourly knock silent (§6.1) |
| §2.11 two env lines in `nightly.yml` and `weekly.yml` | **Five** env lines, identical in `nightly.yml`, `weekly.yml` and `knock.yml` (§3.2). `_workflows_secrets` must learn the one `NIGHT_PERSON_CHECK` expression, which it rejects today (§8.1, a correction) |
| No mid-day run (the brief) | **Unchanged and restated.** A lift at 14:47 clears the record within the hour. The full website fetch still waits for the next night's export (the timer starts the night at 08:17 UTC; night-clock's asking hours end at 12:00, nc `721`). The database keeps the site current on the mornings while the record stands |

---

## 1. The ladder

### 1.1 The settings

These are repository variables, so the owner changes them in GitHub without a commit, as with `NIGHT_KNOCK` (design_final §2.11). Each workflow passes the raw value. `refusal.py` holds the defaults and is the only place the numbers live.

| Variable | Default | Allowed values | Meaning |
|---|---|---|---|
| `KNOCK_HOURLY_HOURS` | 48 | whole number 0–384 | For this many hours after the record's start (`since`), the rung is 1 hour. 0 means no hourly phase |
| `KNOCK_EVERY_HOURS` | 6 | 1, 2, 3, 4, 6, 8, 12 or 24 (it must divide 24, so rungs fall at the same UTC times each day) | The rung after that |
| `KNOCK_DAYS` | 16 | whole number 1–16 | At `since + KNOCK_DAYS × 24 h` the record is a person's: no knock, no database. It replaces `HELD_MOST_HOURS` |

**How they are read.**
- `refusal.knock_settings()` returns `(hourly_h, every_h, days, why)`.
- Unset or empty means the default.
- Anything else that is not a plain decimal in range (`"5"` for `KNOCK_EVERY_HOURS`, `"48h"`, `" 48"`, `"-1"`, `"17"` for days) gives `why`, a sentence naming the variable and its value. `knock_on()` is then false: every record is a person's (`whose()`, condition 7). The third check emails, as with the switch turned off.
- Same rule as `NIGHT_KNOCK`: an unexpected value reads as off.

**`KNOCK_DAYS` is capped at 16.** It closes the database door too (§2.2 of design_final). §4's reasoning about website-only pieces aging set 16 days as the outer bound. Lowering it is the owner's to do freely. Raising it is a design change, not a setting (open question).

**Constants in `refusal.py`, not settings:**
- `KNOCK_ANCHOR`: the daily window's start less `START_MARGIN_MINUTES`, read from `NIGHT_WINDOWS` (today 07:30 UTC), so it moves with the window.
- `KNOCK_MINUTES = 2`.
- `KNOCK_JOB_MINUTES = 15`, the knock job's `timeout-minutes` (preflight holds the two equal).
- `KNOCK_SETTLE_MINUTES = 60`: how long before the last window's close a record must have been noted for an hourly knock to test it (§4.2). It is a margin on how long a drop night runs after its record, not a measurement (§4.2 says why an hour is ample).
- `CLAIM_SLACK_MINUTES = 5`: the claim also asks the gate this much later, so that the child, starting seconds after, does not decline on the clock or the rung (§1.6).
- `HOURLY_SILENT_HOURS = 10`: the open hourly minutes after a knock fell due, with no hourly entry, that make the night say the hourly knock has stopped (§6.1).
- `RELAPSES_MOST = 4`.
- `RELAPSE_HOURS 168` and `RETRY_AFTER_MOST 160 h`, both unchanged.
- `KNOCK_LATEST (11, 18)`, unchanged, for the night's caller only.
- `KNOCK_BY_ENV = "GRANITE_KNOCK_BY"`.
- `KNOCK_NOT_NOW = STOOD_DOWN` (4, `refusal.py:464`).
- Removed: `KNOCK_HOURS`, `KNOCKS_MOST`, `HELD_MOST_HOURS`.

### 1.2 Rungs

`S(t)`, the rung size at time `t`, is 1 h while `t − since < KNOCK_HOURLY_HOURS`, and `KNOCK_EVERY_HOURS` after.

`rung(t, S) = floor((t − KNOCK_ANCHOR) / S)`.

Rungs are aligned to the UTC clock at 07:30, not to `since`. With the defaults:
- **First 48 h:** hour-long rungs from :30 to :30. The hourly runs at :47 sit 17 minutes into a rung, so a run up to 43 minutes late is still in its own rung.
- **After 48 h:** four rungs a day: 07:30–13:30, 13:30–19:30, 19:30–01:30 and 01:30–07:30.

The first of those is exactly the night's window with its start margin. In it only the night knocks, and the other three rungs are the hourly workflow's. So the night's knock and the hourly ones can never share a rung by accident of timing.

### 1.3 When a knock is due: `knock_due(d, k, now)`

- `since` is `k["current"]["since"]`: the record's start, carried across relapses (§2.7 of design_final).
- `last` is the latest failed request: the larger of the record's own `epoch` (the drop, or a relapse's drop) and the `epoch` of every knock in `current.knocks`. Every knock counts except one marked `"not asked"`. A `"claimed"` knock counts.

A knock is due at `now` when **all** hold:
1. `now < since + KNOCK_DAYS × 24 h` (the cap);
2. `now ≥ last + retry_after`, when the record or the last knock carried one (503 only, ≤ 160 h; §2.8 of design_final);
3. `rung(now, S(now)) > rung(last, S(now))`: `now` is in a later rung than the last failed request, both measured in the rung size that applies **now**. So at the switch to 6-hour rungs, a knock made earlier in the same 6-hour rung blocks the next one;
4. `now − last ≥ S(now) / 2`: at least 30 minutes apart in the first 48 h, 3 hours after. GitHub runs late runs in bunches (`workers/night-timer/README.md:3-8` saw 5–7 h late), and a person's dispatch can land right after a scheduled run, so this floor stops two knocks either side of a rung boundary;
5. no knock in `current.knocks` is `"claimed"` and younger than `KNOCK_JOB_MINUTES`. That one is still in flight somewhere.

**A run's own claim is not counted in that run.** In the run that made it (same `GITHUB_RUN_ID` and `GITHUB_RUN_ATTEMPT`), its own `"claimed"` entry is left out of `last`, out of condition 5 and out of `whose()`'s stuck-claim rule. Otherwise the knock would refuse itself: its own claim, seconds old, is in the current rung.

**`knock_due` returns `(bool, due_epoch)`.** `due_epoch` is the earliest `t ≥ now` meeting 1–4. Compute it by testing, in time order, the candidates `now`, the next rung starts in each phase, `last + S/2`, `last + retry_after` and the phase switch `since + KNOCK_HOURLY_HOURS`; each condition is monotone within a phase. It is `None` once condition 1 fails first, and the record is then a person's.

**Only the callers know the hours.** `knock_due` ignores the windows. The night may knock only 08:00–11:18 UTC; the hourly workflow only outside the windows (§4.2).

**`knock_schedule(d, k)`** no longer lists dates. It returns the pattern in words, for the day-0 email and the page: "one request an hour outside 07:30–13:30 UTC until <since+48 h>, then one in each of the six-hour spans from 07:30, 13:30, 19:30 and 01:30 UTC, until <since+16 d>, when the record is yours". A Monday also has its 03:30–06:30 UTC quiet hours.

### 1.4 `whose()`, condition 6, rewritten

design_final §2.2 condition 6 read: "`k` has no `person`, fewer than 4 knocks, and its `since` is under 384 h ago". It becomes:

6. `k` has no `person`; `now < since + KNOCK_DAYS × 24 h`; `current.relapses < RELAPSES_MOST`; and no knock in `current.knocks` is `"claimed"` and older than `KNOCK_JOB_MINUTES` (§1.6).

Condition 7 (`knock_on()`) now also requires `knock_settings()` to give no `why` (§1.1). Everything else in §2.2 stands, rule A included.

### 1.5 Why there is no knock count, and the relapse count that replaces it

**No knock count.** With hour-long rungs, a cap of four knocks would end the method on its first afternoon. The count is bounded instead by the rungs: one knock per rung, at most 94 rungs in 16 days with the defaults (§2). The simulation drives the ladder and asserts that bound (H5).

**`RELAPSES_MOST = 4` replaces the count's other job, bounding a flapping server.**
- Under design_final, each relapse needed a lifting knock and knocks were capped at four, so a chain had at most four relapse nights.
- Hourly knocks would otherwise allow one relapse night a day for 16 days.
- `note()`'s relapse carry (design_final §2.7) adds `current.relapses += 1`. The fourth relapse in a chain makes the record a person's at once, so the third check emails.
- This keeps the approved flapping bound. It is not a new rule, but it is new code, so it is listed for the owner (open question).

### 1.6 The claim: no hourly knock the bucket has not heard of first

**Why it is needed.** An hourly runner is a new way to lose the knock's record. Suppose the knock job's last `state-up` fails after the request. The next hour's run reads a bucket with no trace of that knock, and knocks again. In the six-hour phase that would be up to six times the rate, for as long as writes fail. If the lost answer was a 403, it would be a second request to a server that has just said no.

**The rule.** For the hourly caller:
1. `refusal.py --knock-claim` applies the same gate as the knock (§4.2), **twice: at `now` and at `now + CLAIM_SLACK_MINUTES`**, with the same `knocks.json`. Both must pass. It then appends to `current.knocks` an entry `{"utc", "epoch", "run_id", "attempt", "by": "hourly", "url", "answer": "claimed"}`.
   - The second reading is the margin the child does not keep. The clock part then needs `now + 5 + KNOCK_MINUTES` minutes clear of every window and its start margin, not `now + 2`. The rung part refuses a claim in the five minutes before the switch to `KNOCK_EVERY_HOURS` rungs (`since + KNOCK_HOURLY_HOURS`) and before the last day ends, where `knock_due()` changes its answer.
   - A setting changed by the owner should not split a claim from its child: both steps are in one job and read the same workflow `env` (*guess* that GitHub evaluates `vars.` there once for the job, not per step). If it does split them, rule 5 turns the claim into "not asked".
2. A separate step sends it with `cloud.py state-up`.
3. Only if that step succeeded does the knock step run.
4. The child's `knocking()` finds this run's own `"claimed"` entry (same `run_id` and `attempt`, last in the list) and turns it into `"no answer"` before the request, instead of appending a second one. `knocked()` then writes the answer, as in design_final.
5. **A claim the child did not use is marked "not asked"** (the red team's third finding). A step after the knock step, `refusal.py --knock-unclaim`, runs `always()` once the claim was sent, and before the last state-up. It finds this run's own entry. If that entry still reads `"claimed"`, it rewrites it as `"not asked"`, with "the knock step ended before its request". Any other entry is left alone.
   - This is safe because `knocking()` writes first (design_final §2.4): the entry stops reading `"claimed"` before the request is made. So an entry still `"claimed"` once the child has exited, for any reason (the gate declined, exit 4; the lock was held; a crash; the step's 3-minute kill before `knocking()`), means no request was made.
   - A `"not asked"` entry counts nowhere (§1.3), so the ladder and `whose()` are as if no claim had been made.
   - What is left as `"claimed"` in the bucket is only a job that died before this step, or a state-up that failed after it. Those stay a person's after `KNOCK_JOB_MINUTES`, as below.

**Afterwards, in the bucket:**
- A `"claimed"` entry is one whose answer never reached the bucket.
- Within `KNOCK_JOB_MINUTES` it is in flight: no other knock is due (§1.3, condition 5).
- After that, **the record is a person's**: "the answer to the knock at <utc> (run <id>) never reached the bucket, so it is taken as the worst answer". The third check emails.
- This happens only if R2 failed seconds after it had just accepted the claim, or the runner died mid-job. A claim the child declined no longer reaches here (rule 5). It is rare, and it fails in the safe direction.

**The night does not claim.**
- Its step holds no R2 keys (design_final §13), and its knock is the one in the 07:30–13:30 rung, which no hourly knock uses.
- A lost night-knock record therefore costs no extra request in that rung.
- The residual case is a 403 answered to the night's knock whose record reached the bucket through neither "A refusal goes to R2 at once" (`nightly.yml:449-459`, which runs because `archive/refused.json` still exists after a block-type answer) nor the final state-up (`:534-543`), followed by R2 recovering before the next hourly claim. In that case one more request can follow in a later rung. Two writes must both fail and then succeed again, so this is stated, not closed.

---

## 2. The ceilings, recomputed

These come from `hourly_ladder_sim.py`, with the defaults, every knock failing, the night knocking at 08:23 UTC, and the hourly cron at :47.

| | First 48 h | After 48 h | Per chain (16 days) |
|---|---|---|---|
| Knocks | at most 38: 36 hourly, 2 the night's | at most 56: 4 a day, the night's included | **at most 94** (78 hourly, 16 the night's) |
| Per UTC day | at most 19 (18 hourly + the night's); 16 on a Monday. At most 20 if one late run lands just past midnight | at most 4 | — |
| Closest two knocks | 30 min (condition 4) | 3 h | — |
| Requests at a blocked address | — | — | **at most 96** (the 2 drops + 94), against 6 in design_final |

**With the red team's clock rules** (`hourly_ladder_late.py`). The settle rule and the claim's slack only remove knocks, so the ceilings above stand. Over every five-minute start in a week the most per chain is still 94 (96 requests with the drops). A record noted at 08:27 still gets its first hourly knock at 13:47. One noted at 12:29 does too. One noted at 12:31, or at 14:35 by a late fallback night, gets none that day: the next morning's night knocks at its start, and the hourly ones begin at 13:47 the next day (77 knocks in the chain at 14:35).

**Robustness, checked by `hourly_ladder_jitter.py`.** It ran 300 random schedules: hourly runs 0–120 min late, 5 % dropped, extra dispatches by hand, nights at random minutes between 08:21 and 08:59. It never put two knocks in one rung or two knocks under 30 minutes apart, and never more than 4 in a day after 48 h. The most knocks it saw in a chain was 88. **Lateness only makes the ladder gentler. The 16 days are wall-clock, not runs.**

**Other settings, for the owner** (the same simulation):

| Setting | Knocks per chain | Per day, first phase / after |
|---|---|---|
| `KNOCK_HOURLY_HOURS=24` | 79 | 11 / 4 |
| `KNOCK_EVERY_HOURS=4` | 120 | 19 / 6 |
| `KNOCK_HOURLY_HOURS=0` | 64 | 4 / 4 |
| `KNOCK_HOURLY_HOURS=384` (hourly throughout) | 298 | 19 / — |

**Every failure mode.** This replaces design_final §3's table rows and §2.5's "ceiling the numbers give". "Web" is gc.nh.gov at the address that met the refusal.

| Failure mode | Web: this method | SQL | Stale days |
|---|---|---|---|
| **Outage under a day** (29 Oct, if it was one) | 2 on day 0. Then one an hour from 13:47 UTC until one is answered (at most 18 before the next morning's night). The next night is ordinary | none | 1 (the full fetch waits for the next morning) |
| **Outage of one to two days** | 2, then hourly (at most 19 a day). Lifted within the hour of the website answering | database nights while the record stands | 1 |
| **Longer, every knock unanswered** | 2 + at most 38 + at most 56 = **at most 96 in 16 days**, then 0 | database nights on days 1–16 (the 7th emails). Closed at `since` + 384 h | 1, until day 16; then until a person (third check emails) |
| **A block on one GitHub address that shows as drops, other addresses answering** (*guess* that runner addresses vary) | At the blocked address, at most 96 per chain. That is every knock drawn there, plus each relapse night's first request, one per rung (a relapse fills the night's rung, where the night would have knocked). Lifts from elsewhere, then nothing until the next night | database nights between | relapse nights |
| **Flapping** (a knock answered, the next export drops) | Per lift: the lifting knock. Then nothing asks until the next night, so at most one lift a day. That night's export runs up to its first unanswered request: at most 16, one unanswered (the week's one-drop rule). **At most 4 relapse nights per chain** (`RELAPSES_MOST`) | none on relapse nights | a relapse night is stale |
| **GitHub's cron late or bunched** | fewer, never more: one per rung, 30 min / 3 h apart at least | — | — |
| **knock.yml not running** (disabled by a person; GitHub's 60-day pause if its keepalive failed; GitHub's scheduler down; no read-only key) | the night's knock only: at most 1 a day, at most 16 + 2 per chain. That is design_final's behaviour without its 4-knock end. The first night that finds no hourly entry for `HOURLY_SILENT_HOURS` open hours raises one alarm, which emails through the night's check (§6.1) | database | as with it, except on a night that starts after 11:18 (§14, finding 5) |
| **The night starts after 11:18** | its knock is "not asked"; the hourly ones still come | database | — |
| **A record a late night wrote** (noted after 12:30 UTC; GitHub's fallback started nights at 12:42–15:38 on 19–24 Oct, read_holds rank 12) | no hourly knock until the next window has closed; the next morning's night knocks at its start (§4.2) | database | as for any record: the full fetch waits for a morning anyway |
| **A re-run of a knock run** (any kind, up to 30 days later) | none: the knock job runs only on a run's first attempt (§3.1) | — | — |
| **Block page, 403 or 429 on the night** | 1, then 0. The look job finds a person's record and knocks nothing | 0 | until a person |
| **Block page, 403, 429, 3xx, or 503 with the block page, answered to any knock** | that knock, then 0. The third check emails at once, from the job that met it | 0 from then | until a person |
| **Bare 503, no `Retry-After`** | 1, then the ladder (at most 94) | database, to 16 days | 1 |
| **503, `Retry-After` R ≤ 160 h** | 1, no knock before R, then the ladder | database | 1 |
| **503, R > 160 h** | 1, then 0 | 0 | until a person |
| **R2 refuses writes** | no claim, so no hourly knock. The night's knock is still possible, at most 1 a day | — | — |
| **R2 write fails after an hourly knock** | the bucket keeps `"claimed"`: a person's after 15 min, and the third check emails. No further knock | 0 from then | until a person |
| **The night's knock record never reaches the bucket** (both of its state-ups fail) | at most one more request in a later rung, while R2 recovers; §1.6 says why this is not closed | — | — |
| **The Actions API cannot be read** | no hourly knock that hour (the quiet job says busy) | — | — |
| **The race** (§5) | no extra request. At worst one waiting run is cancelled, and its own dead-man's switch reports it | — | — |
| **Switch off, no third check, an invalid setting** | as today: 2, then 0. Plus the third check's email for a record the method was testing | 0 | until a person |
| **Dry runs** (nightly, weekly, `knock.yml` on dev) | 0. A dry `knock.yml` reads the bucket and the run list and knocks nothing | as design_final | — |
| **The laptop** | never beside an hourly knock: the settle rule means every laptop `gc_turn` lets ask has pulled the record; `--clear` there makes the next fetch pull first; netcheck refuses while GitHub may test the copy (§7) | — | — |
| **The weekly under a record** | 0 web | its database pieces while the night tests the record | — |

---

## 3. The knock workflow: `.github/workflows/knock.yml`

### 3.1 Shape

There are four jobs:
- `look` and `quiet` run on `ubuntu-24.04` and take seconds. `look` holds a **read-only** R2 key; `quiet` holds none.
- `knock`, the only one in `gc-night`, runs on `windows-2022`, the night's image and shell. So the one request goes out from the same Python build and pwsh steps as the night's, and the knock job's state-down and state-up are the night's own commands. It runs only on a run's **first attempt**.
- `keepalive` re-enables the workflow, from a daily cron line of its own, so the `actions: write` token is minted once a day and not in every hourly run.

The file is written in the indentation preflight reads (`preflight.py` nc `93218-93225`): jobs 2 in, keys 4, steps 6, a step's env entries 10. Every `uses:` is pinned to the night's commits.

```yaml
# THE HOURLY KNOCK (the person's decision of 29 October 2026: "hourly, so
# that the site can get back to live sooner"). refusal.py, THE NIGHT'S KNOCK,
# says what a knock is and when one is due. This workflow is the second of
# its two callers. The night knocks once at its start; this one knocks at
# :47 past the hour OUTSIDE the night's window. Neither knocks twice in one
# rung, and only while the bucket holds a refusal the night is testing.
# In any hour without one, it reads two files and stops. Its knock waits in
# gc-night like every night and weekly job, and it never queues there
# while a night, a weekly, a dry run or another knock is running or waiting
# (job "quiet"): GitHub keeps one waiting job per group, and a newer one
# cancels the one waiting (nightly.yml's ONE DRY RUN AT A TIME). A re-run
# never reaches gc-night: re-run alone, the knock job would wait there on
# the earlier jobs' old answers, so it runs only on a first attempt. A lift
# clears the record in the bucket; the full fetch waits for the next
# night. There is no mid-day run. To stop only this: Actions -> knock ->
# "..." -> Disable workflow. To stop all testing: the variable NIGHT_KNOCK
# set to off. Either, BEFORE netcheck.py or clearing a refusal early on the
# laptop: two machines asking at once is how the second block happened.

name: knock
run-name: >-
  knock ${{ github.event.schedule == '23 15 * * *' && '(keepalive)'
  || github.event_name == 'schedule' && '(hourly)'
  || (github.ref != 'refs/heads/main' && '(dry run: not main)' || '(by hand)') }}

on:
  workflow_dispatch:
  schedule:
    - cron: "47 * * * *"
    # keepalive only (job keepalive); look skips this run
    - cron: "23 15 * * *"

permissions:
  contents: read

# A knock dry run never reaches gc-night (the knock job's if requires main),
# so it waits in a group of its own and never replaces a nightly or weekly
# dry run waiting in "dry-runs".
concurrency:
  group: ${{ github.ref != 'refs/heads/main' && 'knock-dry-runs' || github.run_id }}
  cancel-in-progress: false

env:
  PYTHONUTF8: "1"
  PYTHONIOENCODING: utf-8
  DRY_RUN: ${{ github.ref != 'refs/heads/main' }}
  NIGHT_KNOCK: ${{ vars.NIGHT_KNOCK || 'on' }}
  NIGHT_PERSON_CHECK: ${{ secrets.HEALTHCHECKS_PERSON_URL != '' && 'set' || 'none' }}
  KNOCK_HOURLY_HOURS: ${{ vars.KNOCK_HOURLY_HOURS }}
  KNOCK_EVERY_HOURS: ${{ vars.KNOCK_EVERY_HOURS }}
  KNOCK_DAYS: ${{ vars.KNOCK_DAYS }}

jobs:
  look:
    name: is a refusal waiting for a knock
    if: github.event.schedule != '23 15 * * *'
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    outputs:
      go: ${{ steps.look.outputs.go }}
      until: ${{ steps.look.outputs.until }}
    steps:
      - name: Check out main, only what the look reads
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with:
          fetch-depth: 1
          persist-credentials: false
          sparse-checkout-cone-mode: false
          sparse-checkout: |
            refusal.py
            _paths.py
            cloud_kit.json
            requirements-r2.txt
            src/ops/
            src/lib/
      - name: Python 3.14
        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97  # v7.0.0
        with:
          python-version: "3.14"
      - name: boto3 and its dependencies, each by its hash
        shell: bash
        run: python -m pip install --disable-pip-version-check --no-input --require-hashes -r requirements-r2.txt
      # A READ-ONLY KEY (the red team of 29 October 2026): this job runs about
      # 24 times a day and writes nothing to the bucket, so it never holds the
      # keys that write the kit main's nights build and publish from. Without
      # the read-only key it says so and looks no further; the night notices
      # the silence (refusal.HOURLY_SILENT_HOURS).
      - name: Read the state files from R2, with a key that cannot write
        id: statedown
        shell: bash
        env:
          R2_ACCOUNT_ID: ${{ secrets.R2_ACCOUNT_ID }}
          R2_ACCESS_KEY_ID: ${{ secrets.R2_READ_ACCESS_KEY_ID }}
          R2_SECRET_ACCESS_KEY: ${{ secrets.R2_READ_SECRET_ACCESS_KEY }}
          R2_BUCKET: ${{ secrets.R2_BUCKET }}
        run: |
          if [ -z "$R2_ACCESS_KEY_ID" ] || [ -z "$R2_SECRET_ACCESS_KEY" ]; then
            echo "read=none" >> "$GITHUB_OUTPUT"
            echo "No read-only R2 key (R2_READ_ACCESS_KEY_ID, R2_READ_SECRET_ACCESS_KEY): no hourly knock."
            exit 0
          fi
          python src/ops/cloud.py state-down
          echo "read=ok" >> "$GITHUB_OUTPUT"
      - name: Whose is the refusal, and is a knock due now
        id: look
        if: steps.statedown.outputs.read == 'ok'
        shell: bash
        run: python refusal.py --knock-look --person-file logs/alert-person.txt >> "$GITHUB_OUTPUT"
      - name: Tell the "refusal is yours" check when one has become a person's
        if: always() && env.DRY_RUN == 'false' && steps.look.outcome == 'success'
        shell: bash
        env:
          HC_PERSON_URL: ${{ secrets.HEALTHCHECKS_PERSON_URL }}
        run: |
          if [ "$GITHUB_REF" != "refs/heads/main" ]; then
            echo "A run of $GITHUB_REF, not refs/heads/main, is a dry run: no ping."
            exit 0
          fi
          if [ -z "$HC_PERSON_URL" ]; then
            echo "No HEALTHCHECKS_PERSON_URL secret, so no ping."
            exit 0
          fi
          if [ -s logs/alert-person.txt ]; then
            if ! curl -fsS -m 15 --retry 3 -o /dev/null --data-binary @logs/alert-person.txt "$HC_PERSON_URL/fail"; then
              echo "Healthchecks did not answer."
            fi
          fi
          exit 0

  quiet:
    name: is a night, a weekly, a dry run or another knock running or waiting
    needs: look
    if: ${{ !cancelled() && needs.look.outputs.go == 'true' }}
    runs-on: ubuntu-24.04
    timeout-minutes: 3
    permissions:
      actions: read
    outputs:
      quiet: ${{ steps.runs.outputs.quiet }}
    steps:
      # The LAST thing before the knock joins gc-night: nothing may follow it
      # in this job, and the knock job needs this job's answer.
      - name: List the runs that hold gc-night or wait for it
        id: runs
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
          SELF: ${{ github.run_id }}
          UNTIL: ${{ needs.look.outputs.until }}
        run: |
          d=$(mktemp -d)
          since=$(date -u -d '2 days ago' +%F)
          busy() { echo "quiet=false" >> "$GITHUB_OUTPUT"; echo "$1: no knock this hour"; exit 0; }
          gh api -X GET "repos/$REPO/actions/workflows/nightly.yml/runs" -f created=">=$since" -f per_page=100 > "$d/nightly.json" || busy "the nightly's runs could not be listed"
          gh api -X GET "repos/$REPO/actions/workflows/weekly.yml/runs" -f created=">=$since" -f per_page=100 > "$d/weekly.json" || busy "the weekly's runs could not be listed"
          gh api -X GET "repos/$REPO/actions/workflows/knock.yml/runs" -f created=">=$since" -f per_page=100 > "$d/knock.json" || busy "the knock's runs could not be listed"
          # (the open runs' ids, then each one's jobs, then the decision: §3.4)
          ...
```

```yaml
  knock:
    name: the knock
    needs: [look, quiet]
    # NO RE-RUN REACHES GC-NIGHT (the red team of 29 October 2026): re-run on
    # its own, up to 30 days later, this job would join gc-night without a
    # fresh look by quiet. The next hourly run does the work instead.
    if: ${{ !cancelled() && github.run_attempt == '1' && needs.quiet.outputs.quiet == 'true' && github.ref == 'refs/heads/main' }}
    runs-on: windows-2022
    timeout-minutes: 15
    concurrency:
      group: gc-night
      cancel-in-progress: false
    steps:
      - name: Check out main
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with:
          fetch-depth: 1
          persist-credentials: false
      - name: Set the clock to New Hampshire's
        run: |
          tzutil /s "Eastern Standard Time"
          exit $LASTEXITCODE
      - name: Python 3.14
        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97  # v7.0.0
        with:
          python-version: "3.14"
      - name: boto3 and its dependencies, each by its hash
        run: |
          python -m pip install --disable-pip-version-check --no-input --require-hashes -r requirements-r2.txt
          exit $LASTEXITCODE
      - name: Bring the state files down from R2
        id: statedown
        env:
          R2_ACCOUNT_ID: ${{ secrets.R2_ACCOUNT_ID }}
          R2_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}
          R2_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}
          R2_BUCKET: ${{ secrets.R2_BUCKET }}
        run: |
          python src/ops/cloud.py state-down
          exit $LASTEXITCODE
      - name: Claim the knock here, if it may go now
        id: claim
        env:
          GRANITE_KNOCK_BY: hourly
        run: |
          python refusal.py --knock-claim >> $env:GITHUB_OUTPUT
          exit $LASTEXITCODE
      - name: The claim goes to R2 before anything is asked
        id: claimsent
        if: steps.claim.outputs.claimed == 'true'
        env:
          R2_ACCOUNT_ID: ${{ secrets.R2_ACCOUNT_ID }}
          R2_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}
          R2_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}
          R2_BUCKET: ${{ secrets.R2_BUCKET }}
        run: |
          python src/ops/cloud.py state-up
          exit $LASTEXITCODE
      - name: The knock, one request
        id: knock
        if: steps.claimsent.outcome == 'success'
        timeout-minutes: 3
        env:
          GRANITE_KNOCK_BY: hourly
        run: |
          python src/fetch/gc_web/snapshot_gencourt.py --knock
          $rc = $LASTEXITCODE
          Write-Output "The knock ended $rc: 0 lifted, 1 not answered, 2 a person's, 4 not asked."
          if ($rc -in 0, 1, 2, 4) { exit 0 }
          exit $rc
      # A CLAIM THE CHILD DID NOT USE IS NOT A KNOCK. knocking() turns this
      # run's "claimed" into "no answer" before its request, so one still
      # "claimed" now was never asked: it becomes "not asked", and the next
      # look does not take it for a lost answer.
      - name: A claim the knock did not use is marked not asked
        if: always() && steps.claimsent.outcome == 'success'
        env:
          GRANITE_KNOCK_BY: hourly
        run: |
          python refusal.py --knock-unclaim
          exit $LASTEXITCODE
      - name: Send the knock, and a lift, to R2
        if: always() && steps.claimsent.outcome == 'success'
        env:
          R2_ACCOUNT_ID: ${{ secrets.R2_ACCOUNT_ID }}
          R2_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}
          R2_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}
          R2_BUCKET: ${{ secrets.R2_BUCKET }}
        run: |
          python src/ops/cloud.py state-up
          exit $LASTEXITCODE
      - name: What the refusal is now
        if: always() && steps.statedown.outcome == 'success'
        run: |
          python refusal.py --person-line --person-file logs/alert-person.txt
          exit $LASTEXITCODE
      - name: Tell the "refusal is yours" check when this knock made it a person's
        if: always() && env.DRY_RUN == 'false' && steps.statedown.outcome == 'success'
        env:
          HC_PERSON_URL: ${{ secrets.HEALTHCHECKS_PERSON_URL }}
        run: |
          if ($env:GITHUB_REF -cne 'refs/heads/main') {
            Write-Output "A run of $env:GITHUB_REF, not refs/heads/main, is a dry run: no ping."
            exit 0
          }
          if (-not $env:HC_PERSON_URL) {
            Write-Output "No HEALTHCHECKS_PERSON_URL secret, so no ping."
            exit 0
          }
          $said = (Test-Path 'logs/alert-person.txt') -and ((Get-Item 'logs/alert-person.txt').Length -gt 0)
          if ($said) {
            curl.exe -fsS -m 15 --retry 3 -o NUL --data-binary "@logs/alert-person.txt" "$env:HC_PERSON_URL/fail"
          }
          exit 0

  keepalive:
    name: keep the schedule alive
    # Only the daily line's run: the write token is minted once a day.
    if: github.event.schedule == '23 15 * * *'
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    permissions:
      actions: write
    steps:
      - name: Re-enable this workflow, once a day
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
        run: |
          if gh api --method PUT "repos/$REPO/actions/workflows/knock.yml/enable" > /dev/null; then
            echo "knock.yml re-enabled"
          else
            echo "knock.yml could not be re-enabled"
            exit 1
          fi
```

### 3.2 Triggers, the minute, the env, the secrets

- **Triggers.** `schedule` and `workflow_dispatch` only, as `_workflows_permissions` requires (`preflight.py` nc `93436-93444`). Two cron lines: `47 * * * *`, the hourly look, and `23 15 * * *`, whose run does only the keepalive (`look` skips it by `github.event.schedule`, so `quiet` and `knock` are skipped behind it).
  - A dispatch on `main` knocks only when a knock is due, the same as the hourly run.
  - A dispatch on any other branch is a dry run. It reads the bucket and the run list, then says what it would do.
  - Dispatching it is a person's act. The assistant guard already asks before `gh workflow run` (`.claude/hooks/guard.py:229-233`) and before any edit under `.github/workflows` (`:328-329`).
  - **Re-running it is not, today.** The guard returns allow for `gh run rerun 123 --failed`, `gh run rerun 123 --job 456` and `gh run rerun 123` (its `decide()`, run offline on night-clock's `guard.py`; the `gh` rule at `:229-233` names `workflow run`, not `run rerun`). The knock job's `github.run_attempt == '1'` makes any re-run harmless here; the guard row is still proposed (§10, item 12). The same check found `gh run cancel 5` allowed too, which could cancel a waiting night; that is not this design's, and is listed for the owner beside it.
- **The minute is 47.**
  - It avoids :00, where scheduled runs "start late or are dropped" (`nightly.yml:14-16`); :30, a rung boundary (§1.2); and :17, where the night, the weekly and the timer start. So a knock never queues in the minute a night does.
  - It is past :30, so the first run after the daily window closes at 13:30 is 13:47, not 14:xx.
  - It is 17 minutes into its rung (§1.2), so a run up to 43 minutes late is still in its rung.
  - The last run before the 07:30 margin is 06:47. On a Monday, 02:47 is the last before the 03:30 margin, and 06:47 is the first after the 06:30 end.
- **Env.** Five lines, identical in `knock.yml`, `nightly.yml` (beside `DRY_RUN`, `:174`) and `weekly.yml` (beside `:88`): `NIGHT_KNOCK`, `NIGHT_PERSON_CHECK` and the three settings. `DRY_RUN` is the weekly's line (`weekly.yml:88`). Only `refusal.knock_settings()` and `knock_on()` read the five.
- **Secrets, all repository secrets, each only in a step's own env** (`_workflows_secrets`; its regex at nc `93403` already allows a step's env name to differ from the secret's, as `R2_ACCESS_KEY_ID: ${{ secrets.R2_READ_ACCESS_KEY_ID }}` does):
  - in `look`'s one state-down step: `R2_ACCOUNT_ID`, `R2_BUCKET`, and the **new read-only pair** `R2_READ_ACCESS_KEY_ID` and `R2_READ_SECRET_ACCESS_KEY` (§6.2), under the names `cloud.py` reads. Never the write keys;
  - in the knock job's state-down and two state-up steps: the four existing R2 secrets, which it needs to send the claim, the knock and a lift;
  - `HEALTHCHECKS_PERSON_URL`, in the two ping steps;
  - never `HEALTHCHECKS_URL`: a knock that succeeds must never stand in for a night (`_workflows_healthchecks` docstring, nc `94699-94716`);
  - never `HEALTHCHECKS_WARN_URL`, `HEALTHCHECKS_PUBLISH_URL`, `CLOUDFLARE_*` or `YOUTUBE_API_KEY`.

  The R2 keys and the third check's URL must be **repository** secrets, not environment secrets: these jobs have no `environment:`. The weekly already reads the R2 keys with none (`weekly.yml:97-143`), so they are.
- **Packages.** `look` and `knock` install from **`requirements-r2.txt`**, a new tracked file: `boto3==1.43.103` and each of its dependencies (botocore, s3transfer, jmespath, urllib3, python-dateutil, six) pinned, each with `--hash=sha256:…`, installed with `--require-hashes`. `requirements.txt` pins boto3 alone, so today every install takes the newest of those six; an hourly job would take a bad release within the hour, holding R2 keys.
  - *Guess:* that all seven are pure-Python wheels (`py3-none-any`), so one set of hashes serves both runners. The builder confirms it with `pip download` before writing the file; if one is not, the file carries both wheels' hashes.
  - The night's and the weekly's `pip install -r requirements.txt` and the publish job's `boto3==1.43.103` (`nightly.yml:682`) have the same gap. They hold the same keys once a day. Moving them to hash-pinned installs is a separate change, listed for the owner (§15), not part of this branch.
- **Permissions.**
  - Top level: `contents: read`.
  - `quiet`: `actions: read`, to list runs and their jobs with GET.
  - `keepalive`: `actions: write`, to enable itself, only in the daily keepalive run.
  - These are the two shapes `_workflows_permissions` already allows (nc `93463-93477`).
- **Run-level concurrency.** Off `main`, a run waits in **`knock-dry-runs`**, a group of its own; on `main`, its run id, as the weekly's expression (`weekly.yml:68-70`) does. Sharing `dry-runs` would buy nothing, since a knock dry run never reaches `gc-night` (its `knock` job requires `main`), and a newer run in `dry-runs` cancels the one waiting there: a nightly or weekly dry run. `_workflows_dry_runs_wait` is amended to allow this (§8.2).
- **keepalive.** GitHub pauses a public repository's schedules after 60 days without activity (`nightly.yml:794-799`). `nightly.yml`'s keepalive re-enables only itself (`:796-799`, deliberately). So `knock.yml` carries its own, in the `23 15 * * *` run only. A workflow the person disabled runs no keepalive, so it stays off; the night says so (§6.1).

### 3.3 `look`: in seconds, and read-only

- **It reads the bucket only, through the night's own `cloud.py state-down`** (`cloud.py:1995-2047`), which writes nothing to the bucket (its only bucket call is `get_bytes`, `:2009`). It brings `state/refused.json` and `state/knocks.json` down with the rest of `state/` (a few small files). It does so with the **read-only key** (§3.2), so even a compromised install in this job cannot write the bucket. *Guess, until the dev dry run shows it:* that `make_bucket()` makes no write of its own when it opens R2; the dry run of §10 step 5 runs `look` with the read-only key and must read `state/` cleanly.
- **`refusal.py --knock-look`** prints to `$GITHUB_OUTPUT`:
  - `go=true` only when all hold: `GITHUB_ACTIONS` is `true`; not a dry run (`DRY_RUN != "true"` and `GITHUB_REF == "refs/heads/main"` exactly); a record is on file; `whose() == "night"`; `knock_due()` is true now; the hourly gate allows it now, its settle rule included (§4.2); and `until − now ≥ 0`.
  - `until`: the start of the next blocked span (next window start less 30 min) less `KNOCK_JOB_MINUTES` and `KNOCK_MINUTES`, as an epoch.
  - `why`, one sentence.

  It writes `logs/alert-person.txt` from `refusal.person_line()` (§6), but only when the hourly clock of §4.2 allows; inside the night's hours it leaves the file empty. The night reports a record itself, from the state it is about to send, and while a night runs the bucket the look reads can be minutes stale: a record the night's knock lifted at 08:23 stays there until the night's state-up. On a dry run it still says whose the record is and when a knock would be due, which is the dev dry run's proof (§10).
- **"In seconds" is said plainly.** With nothing on file the decision takes under a second, but the job takes about half a minute in all (*guess*, not measured), most of it setting up Python and boto3.
  - A `curl --aws-sigv4` HEAD of `state/refused.json` would take about two seconds. It would be a second R2 client that no check could hold, so it is not used.
  - The sparse checkout keeps each run to the five paths the look needs, not 137 MB × 24 a day. H8 runs `--knock-look` in a tree holding only those paths, so a new import fails a check, not a night.
- **No record, a person's record, not due, inside the hours, a record not yet settled, or no read-only key:** `go` is false or empty, and `quiet` and `knock` are skipped. The run is green. About 25 such runs a day show on the Actions tab (24 hourly and the keepalive's).

### 3.4 `quiet`: the Actions API, and why it is the last step before the group

**The trap** is the one the night's own comment names (`nightly.yml:129-139`). GitHub keeps at most one waiting job per concurrency group, and a newer one cancels the one waiting. So a knock job that queued in `gc-night` while a night held the group and another night waited would cancel the waiting night.

**The rule:** the knock job is queued only when no `gc-night` job of any workflow is running or waiting.

The `quiet` job:
1. Lists the runs of `nightly.yml`, `weekly.yml` and `knock.yml` created in the last two days (three literal `gh api -X GET …/actions/workflows/<file>/runs` calls).
2. Takes every run whose `status` is not `completed`, other than its own (`SELF`).
3. Lists each one's jobs (`gh api -X GET repos/$REPO/actions/runs/<id>/jobs`).
4. Writes `quiet=true` only when **every** one of these holds:
   - every list was read, and no list says it holds more runs than it returned (`total_count` > what came back);
   - each open run lists a job named one of `GC_NIGHT_JOBS` = `"the night"` (`nightly.yml:228`), `"Sunday's fetches"` (`weekly.yml:98`) or `"the knock"`, and every such job is `completed` (skipped counts as completed).

     A run with no such job listed yet counts as busy: one still waiting in `dry-runs` (or a knock dry run in `knock-dry-runs`) at the run level, or a scheduled run whose `started` job (`nightly.yml:199-225`) has not decided. A run whose night job has finished while its **publish** job waits for approval (status `waiting`, for days) does **not** count: the publish job is not in `gc-night`, and counting the run would stop every knock while a held night waited;
   - `now < until`.

   Any failed call writes `quiet=false`: "a list that cannot be read stands the knock down". That is the opposite of `started`'s rule (`nightly.yml:196-198`), on purpose. Two nights in a row are better than none; a knock skipped for an hour costs nothing.
5. The decision is a short inline `python3` (stdlib; `ubuntu-24.04` has a `python3`). H2 extracts it and runs it on canned API answers.

**Order, and a departure from the brief's list.** The brief listed "read-only bucket check, Actions API skip, window skip". Here the window is judged in `look` (by `refusal.py`, the one definition) and handed on as `until`. The API listing goes last, because its answer is only as good as the seconds between it and the knock job entering the group. Nothing may follow it in `quiet` (H1). The window is judged again, exactly, by the claim and by the child, at the moment of asking (§4.2).

**Rate.** About 3–5 API calls an hour, far under the token's hourly allowance (*guess* at 1,000 an hour per repository for `GITHUB_TOKEN`, from GitHub's documentation).

### 3.5 `knock`: the steps, in order, and why

0. **Only a first attempt.** The job's `if` requires `github.run_attempt == '1'` (§3.1), so no re-run of any kind queues it in `gc-night` on an old `quiet` answer.
1. **Checkout, clock, Python, boto3.**
   - Checkout is `fetch-depth: 1`; the night uses 0, which the knock does not need.
   - The Eastern clock matches the night's, so `cloud.py`'s `replaced/<day>/` folder names agree (`cloud.py:1935`, `datetime.now()`).
   - boto3 and its dependencies come from `requirements-r2.txt` by hash (§3.2). Its boto3 line equals `requirements.txt`'s and the publish job's pin (`nightly.yml:682`); H8 holds the three equal.
2. **state-down** (R2 keys). This is the record and `knocks.json` as they stand, inside the group, after any night or knock before it has sent its state.
3. **Claim** (`refusal.py --knock-claim`, `GRANITE_KNOCK_BY=hourly`, no keys).
   - It applies the gate of §4.2 to this moment and to `CLAIM_SLACK_MINUTES` later (§1.6), and writes `claimed=true|false` and `why`. It exits 0 either way; an unexpected error is 1 and fails the job, visibly.
   - A knock job that waited long in the group (behind a dry run that started in the race window, §5) and woke inside 07:30–13:30 claims nothing here.
4. **The claim goes to R2** (`cloud.py state-up`, keys). It runs only after a claim. If it fails, nothing is asked.
5. **The knock** (`snapshot_gencourt.py --knock`, `GRANITE_KNOCK_BY=hourly`, no keys).
   - One request (§4). The step's `timeout-minutes: 3` is the outer kill; the child's own 120-second kill is the inner one (§4.3).
   - Statuses 0, 1, 2 and 4 are answers, so the step is green. Any other status is a crash and fails the job.
5b. **Unclaim** (`refusal.py --knock-unclaim`, no keys), `always()` once the claim was sent. This run's own entry, if it still reads `"claimed"`, becomes `"not asked"` (§1.6, rule 5).
6. **state-up** (keys), whenever the claim was sent. `lift_refusal()` runs first in `state_up` (design_final §2.6). It moves the bucket's `state/refused.json` to `replaced/<day>/` when this knock lifted it, then sends `knocks.json`.
7. **"What the refusal is now"** (`refusal.py --person-line`, no keys). It writes `logs/alert-person.txt` from the state on this machine after the knock.
8. **Healthchecks.**
   - `/fail`, with that file as the body, when it is non-empty: a block-type answer, the last day reached, the fourth relapse, and so on.
   - Nothing otherwise. Never a plain ping (§6).
   - It comes after state-up, so the email describes what the bucket was told. It is `always()`, so a failed state-up does not silence it.

**Every General Court request in this workflow is in step 5**, under `refusal.hold("the knock")`. On this runner nothing else holds `archive/.lock`, so the child takes it itself (`refusal.py:346-372`), as `snapshot_gencourt`'s normal path does. `knock.yml` names no `gc.nh.gov` URL; `KNOCK_NAME` and `BASE` stay in `snapshot_gencourt.py` (`:104`, `:119`), so `_every_fetcher_checks_refusal`'s reading is unchanged.

---

## 4. The night's knock and the hourly ones: one ladder

### 4.1 One state file

**Both callers write `archive/knocks.json`** (R2 `state/knocks.json`) through `refusal.py` only. Each knock entry gains `by` (`"night"` or `"hourly"`) and `attempt` (`GITHUB_RUN_ATTEMPT`).

**`gc-night` serialises every writer:** the night, the weekly and the knock job. Each takes state down at its start and sends it up before it releases the group. So each reads what the one before it wrote. That is the same argument as design_final §16, now with three job names.

**Size.** `lifted[].knocks` keeps the chain's knocks. At up to 94 entries of about 250 bytes, a lift entry is now up to about 25 KB, not 1 KB. It is still never pruned (design_final §2.6), and at most one is added a day.

### 4.2 The gate, `refusal.knock_gate(by, now=None)`, two modes

`check(who, knock=True)` calls `knock_gate(os.environ.get(KNOCK_BY_ENV))`. So do `--knock-claim` (with the env) and `--knock-look` (with `"hourly"`). No other caller exists (H6's AST case).

Shared conditions, all from design_final §2.4:
- `GITHUB_ACTIONS == "true"`;
- not dry, and ref `refs/heads/main` exactly;
- `MARK` exists and reads;
- `whose() == "night"`;
- `knock_due()`.

The clock, by mode:

| `GRANITE_KNOCK_BY` | Set by | Allowed when |
|---|---|---|
| `night` | `nightly.knock()`, in the child's env, and nowhere else | `night_window()` is the daily window, and the UTC time is before `KNOCK_LATEST` 11:18. Unchanged from design_final §2.4. The parent's `asking_left(42)` stands too |
| `hourly` | `knock.yml`'s claim and knock steps, and nowhere else | `refusal._window_or_soon(now)` is `None` **and** `_window_or_soon(now + KNOCK_MINUTES)` is `None`. That means outside every `NIGHT_WINDOWS` window and its `START_MARGIN_MINUTES` (`refusal.py:695-704`), for the whole two minutes the knock may take. With today's definition: never 07:30–13:30 UTC, nor 03:30–06:30 UTC on a Monday. **And the settle rule:** the record's own `epoch` (refused.json's, the drop or the relapse that wrote it, not the chain's `since`) is at least `KNOCK_SETTLE_MINUTES` before `refusal.last_window_end(now)` (`refusal.py:621-625`) |
| anything else, or unset | — | never |

**The settle rule, and why the laptop needs it** (the red team's first finding).
- The stood-down laptop starts a General Court request outside the windows only when its pull read the bucket after the last window closed (`gc_turn`, `refusal.py:730-744`; `check()` asks it, `:228-233`; the lane asks it before each step, `gc_lane.py:44-54`). Under design_final GitHub knocked only inside a window, where that laptop is barred (`:716-722`), so nothing more was needed.
- An hourly knock asks outside the windows, in the laptop's hours. It is safe there only if every laptop `gc_turn` lets ask holds the record. That holds when the record reached the bucket **before** `last_window_end(now)`: a laptop that may ask then pulled after it, and the pull creates the record on the laptop (`cloud.py:2778-2780`), where the lane and hand fetches stop at it (design_final §2.10).
- **A late night breaks it without the rule.** The export is not clock-gated: `nightly.py` runs the snapshot whatever the hour (nc `1649-1656`); `asking_left` gates only the bill requests and the lists (nc `3994`, `4087`). GitHub's fallback started nights at 12:42–15:38 UTC on 19–24 October (read_holds rank 12, `:34`). A record noted at 14:35 reaches the bucket at about 14:37, after a laptop that pulled at 13:45 last looked.
- **Why an hour is the margin.** The record is noted at `epoch` and reaches the bucket when "A refusal goes to R2 at once" runs (`nightly.yml:449-459`), after `nightly.py` exits. A drop night installs nothing, so it builds nothing (`installed` is false, nc `1733`; the build needs it, nc `1801`), and exits within minutes of the record. If that step fails, the final state-up (`:534-543`) follows kit-up and `--close`. An hour is a margin over minutes, not a measurement. *Said plainly:* a record whose both uploads took longer than an hour would leave a window for a laptop that pulled in between; it needs R2 or kit-up to stall for most of an hour on a drop night.
- **What it costs: nothing for the site.** With today's windows, a record noted after 12:30 UTC gets no hourly knock until the next window has closed. The next morning's night knocks at its start anyway, and the full fetch never comes before that morning (no mid-day run). `hourly_ladder_late.py`: a record at 14:35 gets its first hourly knock at 13:47 the next day; one at 08:27 or 12:29 at 13:47 the same day; the most per chain is unchanged (§2).
- The night's mode needs no such rule: it asks inside a window.

**The two modes' hours are disjoint**: [08:00, 11:18) lies inside the daily window, and `hourly` lies outside it and its margin.
- So a mix-up in a refactor makes a knock refuse; it never widens one. `night` set in `knock.yml` refuses outside 08:00–11:18. `hourly` set in the night refuses inside the window.
- H3 sweeps a week minute by minute and asserts both sets and their disjointness.
- H3 also asserts that `hourly` follows `NIGHT_WINDOWS` when the check moves the windows, so it reads the one definition and no copy.

### 4.3 What changes in the child and in the night's `knock()`

- **A refusal by the gate exits 4** (`KNOCK_NOT_NOW`), not 2. Exit 2 stays only for "a person's for good" (`person` set). Under design_final, both meant exit 2 (§2.4, "exits 2 and asks nothing"; C5 "zero opener calls and exit 2"), and the night read rc 2 as "nothing more, no database, the alert" (§2.3; C6). With an hourly caller that would turn every opening of the window into a false "refusal is yours". The night now reads:
  - 0: lifted;
  - 1: a failed knock, so the held path;
  - 2: a person's;
  - 4: "the knock: not asked: <why>", then the held path while `whose()` is still the night's;
  - 124 (`RUN_KILLED`): a failed knock.
- **The child kills itself at `KNOCK_MINUTES`.** `knock(held)` starts a timer that ends the process with `RUN_KILLED` (124) 120 s after `knocking()` wrote "no answer". So the hourly caller has the same bound the night's `run(timeout=)` gives (nc `1192`, `1239`). The night's outer kill stands.
- **`knocking()`** reuses this run's own `"claimed"` entry (§1.6). The night never has one.
- **`refusal.py --knock-unclaim`** (new, §1.6 rule 5): this run's own entry, still `"claimed"`, becomes `"not asked"`. It touches no other entry, writes a part file then renames, and exits 0 when there is nothing to do.
- **The night's sentences.** The day-0 email gives `knock_schedule()`'s pattern and the date the record becomes a person's at the latest, not four dates. The held line reads "<n> knocks unanswered since <since>; the last at <utc> (<by>); the next due from <utc>". `DB_NIGHTS_MOST`'s sentence (design_final §2.9) names the next knock as "within the hour" in the first phase, otherwise "from <utc>".
- **The night still knocks at its start, whenever its rung allows.**
  - In the first 48 h, its rung is free: the last hourly run before it was 06:47, in the rung before.
  - After 48 h, the 07:30–13:30 rung is the night's, and condition 4 asks 3 h since the last knock. With the 01:47 knock as the last, the night at about 08:23 knocks. If a late 06:47 run knocked instead, the night does not, takes the database, and the 13:47 run is the next.

---

## 5. The race, closed where it can be and bounded where it cannot

**Closed.**
1. **Overlap.** The knock job is in `gc-night`, so it never runs beside a night, a weekly or a dry run. `look` and `quiet` ask nothing of the General Court.
2. **Queueing behind a known run.** `quiet` sees every run of the three workflows that is running or waiting, its `gc-night` job included, and the knock is then not queued.
3. **Inside the hours.** Even a knock job that waited long in the group claims nothing and asks nothing inside 07:30–13:30, or Monday's 03:30–06:30 (§3.5, step 3; §4.2).
4. **The timer's night.** It starts at 08:17 (`workers/night-timer/wrangler.toml:10-11`), inside the hours when no knock job is queued.
5. **A re-run.** Re-running a failed job (or one job) runs it again without the jobs that succeeded, on their old answers, up to 30 days later (GitHub's documentation, read today: re-runs are allowed "up to 30 days after its initial run" and keep "the same `GITHUB_SHA` … and `GITHUB_REF`"). The sentence the red team quoted about successful jobs' outputs was not found on the two re-run pages read today, so that the old `quiet=true` is reused is a *guess*; if it is empty instead, the knock job skips anyway. The knock job's `github.run_attempt == '1'` closes both: no re-run of any kind reaches `gc-night` (H1).

**Bounded, not closed.** The knock job can still cancel a waiting run in one case. Between the last API answer in `quiet` and the knock job entering `gc-night`, two runs must both enter `gc-night`: one that takes the group, and one that waits behind it.
- That interval is the end of one job and the start of the next. It is seconds (*guess*, not measured; GitHub does not document it).
- To cancel a real night, one of those two runs must be a real night: GitHub's late fallback (it ran 12:42–15:38 UTC on 19–24 October, read_holds rank 12), or a person's run by hand of `main`. It must start in the same few seconds as another run.
- Even then:
  - **no request is added**: a cancelled knock asks nothing, and nothing runs beside anything;
  - the cancelled night is reported by the night's own dead-man's switch (`HEALTHCHECKS_URL`), as the existing "still open" case is (`nightly.yml:137-139`; `weekly.yml:64-67`);
  - a cancelled dry run is a person's to start again.

**The existing case, widened a little.** While the knock job holds `gc-night`, a real night that queues behind it can be cancelled by a dry run started by hand. That is the case `nightly.yml:137-139` already leaves open, with the knock as one more holder.
- The knock holds the group about 3–5 minutes (*guess*, a Windows job's start included), and only while a record stands and outside 07:30–13:30. That is at most 18 times a day for two days, then at most 3.
- The real night (08:17) never starts then.

**Not closed, on purpose.** A lease outside GitHub would mean a lock object in R2 that the night takes too. That changes the night job and adds a writer to the night's path, for a case the dead-man's switch already reports. Left as a later option.

**A later option that may close all three at once, unproven here: `queue: max`.** GitHub's concurrency page, read today, describes `queue: max`: "Up to 100 jobs or workflow runs can be `pending` in the concurrency group", in first-in-first-out order (it says start order is not guaranteed), not with `cancel-in-progress: true`. Its only example is at the workflow level; whether it applies to a **job**-level group such as `gc-night` the page does not say. Set on `gc-night` in `nightly.yml`, `weekly.yml` and `knock.yml`, it would close the race above, the re-run case and the open case at `nightly.yml:137-139`. It is not relied on here. Proving it needs a dev dry run with two waiting jobs, and it changes the night's own concurrency, which is the night-clock branch's and the owner's to approve.

---

## 6. Healthchecks, and D5

### 6.1 Who pings the third check

| Pinger | When | What |
|---|---|---|
| The night (design_final §2.9, `nightly.yml:568`'s step) | every real night, at its end | `/fail` with `logs/alert-person.txt` when non-empty; a plain ping when empty; nothing when `--close` wrote no file. Unchanged |
| `knock.yml`, `look` | any hourly run on `main`, **outside the night's hours** (§3.3), whose bucket holds a record **the method was testing** (a `current` chain names its sha) that is now a person's: the last day reached, the switch turned off, an invalid setting, the fourth relapse, a stuck claim | `/fail` only. It repeats each hour until a person clears it, and Healthchecks emails only on the change (`nightly.py` nc `5846-5849`) |
| `knock.yml`, `knock` | the knock it just made gave a block-type answer, or the record otherwise became a person's during the job (its last day reached) | `/fail` only |
| Anything | a dry run | never: the exact-ref guard, as `HC_REF_GUARD` (`preflight.py` nc `94689`), in each ping step |

**`knock.yml` never sends a plain ping.**
- Otherwise a run reading a bucket that a failing night had not yet written could ping "up" a minute after the night's `/fail`, and flap the check.
- So "up" comes only from the night, the morning after a person clears the record.

**`refusal.person_line(d, k, now)`** is the one sentence. It is shared with `person_alerts_of()`.
- It is non-empty when `whose()` is `"person"`.
- For `--knock-look` only, it is non-empty only when `k["current"]` names this record. A kindless or night-met 403 record is the night's to report, and the night does.
- It uses this project's words, never a server's (`nightly.py` nc `5849-5850`).
- For a block-type answer it says the IT office or the Clerk's office may need a message (design_final §2.9).

**When the hourly knock stops: the night says so, once, by email** (the red team's fifth finding).
- `knock.yml` can stop without a sign: disabled by hand, paused by GitHub's 60-day rule (its keepalive cannot run while it is disabled), GitHub's scheduler stalled, or no read-only key (§3.3). Each hourly run's look writes nothing, so the only trace of the workflow running is a `by: "hourly"` entry in `knocks.json`, which a knock or a claim writes.
- **New `refusal.hourly_silent(d, k, now)`**, read by the night at its start. It returns a sentence when all hold: `whose() == "night"`; and, in the 18 hours before today's daily window less its margin (07:30 UTC), at least `HOURLY_SILENT_HOURS` (10) of the hourly minutes (:47) fell after `knock_due()`'s `due_epoch` and were open to the hourly gate (clock and settle rule); and `current.knocks` holds no `by: "hourly"` entry, of any answer, "not asked" included, in those 18 hours.
  - The 10 open hours allow for GitHub's lateness. In October it ran scheduled workflows 5–7 h late (`workers/night-timer/README.md:3-8`). A run 7 h late lands inside the window, where the look claims nothing and leaves no entry. Ten open hours leave at least three that land outside it. *Guess:* that lateness stays under 7 h. If it does not, the sentence is a false alarm, but one that says GitHub's scheduler is failing, which is worth knowing.
  - A record the settle rule holds (§4.2), a `Retry-After` and a person's record give fewer open hours, so no sentence.
- **Routing: an alarm on the first night, the held line after.** On the first night it holds (it did not hold for the 18 hours before yesterday's window), the sentence is one of `alarms()` (nc `5537`). It reads "the hourly knock has not run since <utc of the last hourly entry, or since the record began>; knock.yml may be disabled, paused by GitHub, or without its read-only R2 key; the night still knocks once each morning". An alarm "does not stop the night: the build still goes out, and somebody has to act" (nc `5538-5539`). It is not among the gate's reasons (nc `5589-5590`). It makes the night not clean (nc `5583`), so the night's own check gets `/fail`, and Healthchecks emails on that change. The next night, the same silence is only in `warns_of()`'s held line. The night is then clean again, the check goes back up, and the dead-man's switch is restored after one night.
  - So the person gets one "down" email and one "up" email per stop. That is the cost. While that one alarm stands, a night that failed to run would send no new email; `DB_NIGHTS_MOST` already accepts that.
  - Not the third check: its email means "a refusal is yours", and this is not one. The record stays the night's, and the database stays open.
  - Not the warnings' check alone: it may already be down (design_final §2.9).
- **What the silence costs, said plainly.** The night still knocks once each morning while its rung allows, so the site's freshness changes only on a night that starts after 11:18 UTC and cannot knock (`KNOCK_LATEST`), when an earlier hourly lift would have let it fetch (§14, finding 5). The request count falls to at most 16 + 2 per chain.

### 6.2 D5, the owner's steps

The existing checks' Healthchecks settings are not in the repository. The operator checklist is `reports/cloud/CLOUD_MOVE.md` on the laptop (`nightly.yml:3`; `preflight.py` nc `93228`). The repository says only:
- the night's check is the dead-man's switch whose "deadline catches the first missed night" (`nightly.yml:797-798`);
- the publish check went quiet "two days later" (`nightly.yml:759-761`);
- the follow sender's check has an "hourly period" (`workers/follow/README.md:249`).

So the schedule below is derived from how the third check is pinged, not copied.

1. **In Healthchecks, Add Check.**
   - Name: `a refusal is yours`.
   - Description: "Pinged by the nightly at its end (up, or /fail when a General Court refusal is a person's) and by the knock workflow (/fail only). Down means a person must act; the email's body says why."
2. **Schedule: Simple. Period 1 day. Grace 1 day.**
   - The night pings it once a day, normally about 09:30 UTC. GitHub's fallback has started nights 5–7 h late (`workers/night-timer/README.md:3-8`), so two pings can be about 31 h apart.
   - The knock workflow only ever sends `/fail`, so it never keeps the check up.
   - With 1 + 1 days, the check goes down by silence only after two days with no night reporting, and the night's own check will have emailed first. Such an email means the night stopped reporting, not that a refusal is yours (the `/fail` emails carry a body; a silence one does not).
   - The default grace of an hour would email whenever a night ran late.
3. **Integrations:** the owner's email on, as for the other checks.
4. **Copy the check's ping URL** (`https://hc-ping.com/…`).
5. **In GitHub:** the repository → **Settings → Secrets and variables → Actions → Secrets → New repository secret**. Name: `HEALTHCHECKS_PERSON_URL`. Value: the URL.
   - It must be a **repository** secret. `knock.yml`'s jobs and the weekly have no environment, and a workflow-level `env` cannot read an environment's secrets.
   - Done this way, the URL is never typed into a file or a log. The workflows hand only "set" or "none" to `nightly.py` and `refusal.py`.
6. **Before the merge to `main`:** the dev dry runs (§10) print `NIGHT_PERSON_CHECK set`.
7. **The morning after the merge:** the check shows "up", pinged by the first real night. If it still says "new", the URL is wrong. The method then believes the check is set while nothing arrives, so set `NIGHT_KNOCK` to `off` until it is fixed (design_final §11's sign).
8. **A read-only R2 key for the look job** (the red team's fourth finding).
   - In Cloudflare: **R2 → Manage R2 API tokens → Create API token**, permission **Object Read only**, applied to the kit's bucket only. *Guess:* the menu names, and that the account allows a bucket-scoped read-only token; the red team made the same guess.
   - In GitHub, two more **repository** secrets: `R2_READ_ACCESS_KEY_ID` and `R2_READ_SECRET_ACCESS_KEY`, the token's two values. The account id and the bucket name are the existing secrets.
   - Without them `knock.yml` looks no further each hour and says why in its log; the night's knock goes on, and the night's alarm says the hourly knock is silent (§6.1). So this step is needed for the hourly knock, not for safety.
   - Before the merge: the dev dry run of `knock.yml` (§10 step 5) must read `state/` with this key.

---

## 7. The laptop's `pull` and `send-refusal`

design_final §2.6 stands: the lift is in `state/knocks.json`'s `lifted`, whoever made it, and both commands read it at any age. Hourly lifts can now land at any hour outside 07:30–13:30, so three orders become rules:

1. **`pull_refusal` reads `state/refused.json` first, then `state/knocks.json`.** A lift landing between the two reads is then seen: the copy the pull just took is in `lifted`, so it gets the lift line. In the other order, a copy taken earlier would meet an empty bucket and a `lifted` without its sha, which is the "IS NOT IN THE BUCKET" failure (`cloud.py:2801-2807`). C9 gains this case.
2. **`send_refusal` confirms the bucket holds no refusal, then reads `state/knocks.json`, then puts.** It never sends a sha in `lifted` (design_final §2.6). C9 gains "a lift lands between the pull and the send".
3. **A record in the bucket whose sha is in `lifted` is lifted for every GitHub reader.** `gc_quiet()` and `whose()` treat it as absent, and the next GitHub `state_up` moves it, since `lift_refusal()`'s conditions already hold. This covers a resurrection that lands inside the last two steps' gap. C8 gains it.

**What stops the laptop while GitHub knocks hourly: one rule on GitHub's side, two on the laptop's.**

The earlier text here said "the bucket's record is always written inside a window, so the laptop is stopped by its pull for as long as the hourly knocks run". **That was wrong** (the red team's first finding). A late night writes its record outside the window (§4.2), and a person's `--clear` on the laptop leaves the pull's read time standing. Both now hold:

1. **GitHub's side: the settle rule** (§4.2). An hourly knock tests only a record that reached the bucket before the last window closed. So every laptop that `gc_turn` lets ask (`refusal.py:707-744`) pulled after the record was there, and holds a copy. The lane stops at that copy (`gc_lane.py:402-406`); hand fetches stop at a GitHub record with a kind at any age (design_final §2.10).
2. **The laptop's `--clear` makes the next fetch pull first.** Today `refusal.py --clear` unlinks `MARK` and nothing else about the bucket (`refusal.py:839-859`). The pull's read time stands, so `gc_turn` lets the lane and hand fetches ask at once. The pull's own line warns that "lifting only this one brings it back at the next pull" (`cloud.py:2819-2821`), but nothing makes that pull come first.
   - **Change.** On a stood-down laptop (`stood_down()` not `None`), `--clear` also writes `archive/refusal-cleared.json` (`{"utc", "epoch"}`). `refusal_read()` (`refusal.py:678-692`) returns `None` while that epoch is later than the pull's read. So `gc_turn` says "pull" until a pull reads the bucket again (the pull's own file, `archive/cloud/pull.json`, stays `cloud.py`'s alone).
   - That pull re-creates the laptop's copy when the bucket's record still stands (`cloud.py:2778-2780`), so the laptop stops again; or it shows the record lifted or cleared, and the laptop goes on.
   - `--clear` says so: "the next General Court request here waits for python3 src/ops/cloud.py pull --changes-only, which brings the bucket's refusal back if it still stands: clear that one first with python3 src/ops/cloud.py clear-refusal". The order for_owner gives (bucket first, then the laptop) is unaffected.
   - Off a stood-down laptop, and on GitHub, `--clear` is unchanged (`_governing()` is `None` there, `refusal.py:545-566`).
3. **netcheck refuses beside a test.** netcheck consults neither the refusal record nor the window (its imports, `netcheck.py:45-57`), yet design_final §4 (`:432`) sends the person to it before clearing a record early, which is exactly while the hourly knocks run. It makes 8 requests over two hosts, 7 with a browser User-Agent (read_refusal). On a stood-down laptop, netcheck now:
   - stops with `gc_turn()`'s sentence when that is not `None` (inside a window, in the half hour before one, or before a pull since the last window closed, a `--clear` included). That is the laptop's existing one-fetch-at-a-time rule, which netcheck alone skipped;
   - stops when `MARK` holds a record GitHub may be testing (`machine == "github"`, `kind` in `RESUMABLE`, `ref == "refs/heads/main"`, not `dry`), unless the person passes `--knock-stopped`. The laptop cannot read `NIGHT_KNOCK` (`knock_on()` is false there, design_final §2.10), so it judges by the copy its last pull took, and the flag is the person's word. The sentence says: "GitHub may be testing this refusal itself, once an hour. Two machines asking at once is how the second block happened. Set the GitHub variable NIGHT_KNOCK to off, or disable the knock workflow, wait until the Actions tab shows no knock run in progress (a knock job lasts 15 minutes at most), then run python3 netcheck.py --knock-stopped."
   - Off a stood-down laptop it is unchanged. D6's guard row (ask before `netcheck.py`) stands.
4. **The person's word, in every place that names an early clear.** for_owner, the CLAUDE.md paragraph (§9), the day-0 email (C11) and pull's line for a GitHub record with a kind say: set `NIGHT_KNOCK` to `off` (or disable `knock.yml`) **before** netcheck or clearing early. Turning `NIGHT_KNOCK` off makes the record a person's at once; the next hourly look sends the third check `/fail`, an email the person expects because they caused it.

The day-0 email's laptop sentence changes with it. design_final's "the laptop's next pull will ask for `python3 refusal.py --clear` there" (§2.9, `:327`; C11, `:556`) described the laptop after a lift. While the record stands it now reads: "nothing is needed on the laptop: its copy stops its fetches until GitHub lifts the record, and its next pull then says so. To check or clear it sooner yourself, first set NIGHT_KNOCK to off."

**`refusal.py`'s status lines** (`main()`, `force()`) name the lifter: "GitHub's knock lifted this refusal at <utc> (hourly)" or "(the night's)".

---

## 8. Preflight

### 8.1 Two existing checks that a correct build fails today

1. **`_workflows_secrets`** (nc `93372-93420`) requires every `secrets.` use to be a step's own env entry of the exact form `NAME: ${{ secrets.NAME }}` (regex at nc `93403`). design_final §2.11's `NIGHT_PERSON_CHECK: ${{ secrets.HEALTHCHECKS_PERSON_URL != '' && 'set' || 'none' }}` at the workflow level fails it.
   - **Amend:** allow exactly that one line, two spaces in, under the top-level `env:`, in each workflow that has a `gc-night` job, and no other expression over a secret.
   - The check's mutation: the same expression at step level, or naming another secret, fails.
   - This was missed in design_final, and the hourly workflow needs the line too.
2. **`_workflows_permissions`** (nc `93423-93483`) passes `quiet` as written (GET only, the literal `actions/workflows/nightly.yml/runs`, no `uses:`), but its message names only the timer's purpose.
   - **Amend:** an `actions: read` job may GET only `…/actions/workflows/<file>/runs` and `…/actions/runs/<id>/jobs`.
   - Name the two jobs that may hold it: `nightly.yml:started` and `knock.yml:quiet`.

### 8.2 Existing checks that `knock.yml` must pass unchanged

- **`_workflows_parse`:** pinned actions, a timeout on every job, runs-on pinned; it runs no `nightly.py`.
- **`_workflows_production`:** it deploys nothing.
- **`_workflows_healthchecks`:** it names no `HEALTHCHECKS_URL`.
- **`_workflows_dry_runs_wait`** (nc `94843-94900`), **amended** (the red team's sixth finding): add `knock.yml` to `WF_RUNS` (nc `94151`):
  - `("schedule", MAIN_REF, {}, False, "knock (hourly)")`;
  - `("workflow_dispatch", MAIN_REF, {}, False, "knock (by hand)")`;
  - `("workflow_dispatch", "refs/heads/dev", {}, True, "knock (dry run: not main)")`.

  Today the check requires every dry run of every workflow with a `gc-night` job to render to `DRY_RUNS_GROUP`. It is amended to require that only of a workflow whose `gc-night` job can run on a dry run. A workflow whose every `gc-night` job's `if` renders false for every dry run in `WF_RUNS` (here, by `github.ref == 'refs/heads/main'`) must instead put its dry runs in a group of its own: not `DRY_RUNS_GROUP`, not `gc-night`, the same for both run ids. Its mutations: `knock.yml` back in `dry-runs`; the `main` test dropped from the knock job's `if` while its dry runs keep their own group (that must fail, because a knock dry run could then reach `gc-night` without waiting in line).
- **`_workflows_skipped_ancestors`** (nc `94906`): `quiet` and `knock` say `!cancelled()`.
- **`_workflows_secrets`**, once amended.
- **`WORKFLOW_SECRETS`** (nc `93229`) gains `HEALTHCHECKS_PERSON_URL` (design_final §5), `R2_READ_ACCESS_KEY_ID` and `R2_READ_SECRET_ACCESS_KEY` (§6.2).

### 8.3 Amended from design_final §6

| # | Change |
|---|---|
| C2 | Replaced by H5 |
| C2b | "a fourth knock" becomes "a fourth relapse" (`RELAPSES_MOST`). A relapse at the carried `since` + `KNOCK_DAYS` × 24 h + 1 h is a person's. `current.relapses` is carried |
| C5 | Every gate refusal exits **4**, with zero opener calls: the record 2 h old, kindless, `DRY_RUN=true`, no `GITHUB_ACTIONS`, `NIGHT_PERSON_CHECK` unset, `GRANITE_KNOCK_BY` unset or `other`. The `night` mode refuses at 11:30, 12:30 and 14:00. The `hourly` mode refuses at 07:30, 07:29 (inside the 2 minutes), 10:00 and 13:29, and on a Monday at 03:30 and 06:29. It allows 13:31 and 07:27. Exit 2 occurs only with `person` set. The child's own kill: an opener that never returns ends at 120 s with 124 and leaves "no answer". The AST case gains "only `nightly.knock()` sets `GRANITE_KNOCK_BY`, to `"night"`; only `knock.yml`'s claim and knock steps set it, to `"hourly"`" |
| C6 | Knock rc 4 means the held path with "not asked" in `v["knock"]`, not the alert. rc 2 with `person` set means "nothing more, no database" |
| C10 | Plus (the red team's first finding): on a stood-down laptop whose pull read the bucket at 13:45, `refusal.py --clear` makes `gc_turn()` at 13:50 return `"pull"`, and `check()` exits 4 (`STOOD_DOWN`); a pull at 13:55 (a folder bucket holding the record, with the read marked `r2` as the test's fake) re-creates the copy, and `check()` exits 2; with the bucket holding none, `check()` passes. Off a stood-down laptop, `--clear` writes no `refusal-cleared.json` and `gc_turn()` is unchanged |
| C11 | The day-0 line names the pattern and the last date, not four dates. Day 0 with an invalid setting behaves as with the switch off. The day-0 line no longer asks for the laptop's `refusal.py --clear` while the record stands; it says "first set NIGHT_KNOCK to off" for an early clear (§7, item 4) |
| C15 | Plus: on a stood-down laptop netcheck makes **zero** requests (its opener faked) and exits non-zero when `gc_turn()` is not `None`, and when `MARK` holds a `machine: "github"`, `kind: "dropped"`, main, not-dry record without `--knock-stopped`. With the flag, and `gc_turn()` `None`, it runs. A kindless or laptop-written copy needs no flag. Off a stood-down laptop it is unchanged |
| C16 | Five lines, identical, in `nightly.yml`, `weekly.yml` and `knock.yml`, and nothing else reads them. `KNOCK_*` come from `vars.` with no fallback in the expression (the defaults are `refusal.py`'s) |
| C18 | Sequence 2 ends at 16 days, not the 4th knock. **New sequence 4:** day 0, then an hourly knock at 14:47 answered with the block page. The knock job's person file is non-empty, so `/fail`, a change, the same day. **New sequence 5:** a chain reaching `since` + 384 h at 08:27. That morning's night's `--close` gives a non-empty file, so `/fail` and a change. The 08:47 to 12:47 looks leave theirs empty (inside the hours), and the 13:47 look's is non-empty: a repeat, no new email. A weekly-started chain (`since` 04:20 on a Monday) reaches its end at 04:20 on the Wednesday sixteen days on; the 04:47 look's file is non-empty, the change |

### 8.4 New checks

Each must fail when its rule is taken out. Each carries that mutation itself: it applies the change to a copy in a temp folder and asserts the check fails, as `_workflows_skipped_ancestors`'s docstring records doing by hand (nc `94917-94918`).

| # | Check | Asserts | Fails when (its mutation) |
|---|---|---|---|
| H1 | `_workflows_knock_order`: **the skip precedes the group** | In `knock.yml`: exactly one job holds `group: gc-night` with `cancel-in-progress: false`. That job's `needs:` includes `quiet`, and its `if` requires `needs.quiet.outputs.quiet == 'true'`, `!cancelled()` and **`github.run_attempt == '1'`**, rendered false for attempts 2 and 3. `quiet` has no `concurrency:` and its last step is the listing (the step that sets `quiet`). `quiet`'s `if` requires `needs.look.outputs.go == 'true'`. No other job runs `snapshot_gencourt.py`. The unclaim step (`--knock-unclaim`, `always()`, after the knock step, before the last state-up) is present | `quiet` dropped from `needs`; the `quiet == 'true'` test dropped; the `run_attempt` test dropped; the group moved to `quiet`; a step added after the listing; the knock run in `look`; the unclaim step dropped or moved after the state-up |
| H2 | `_knock_quiet_decides` | The listing's inline `python3`, run on canned API JSON, gives `quiet=true` only for: nothing open; a run whose night job is completed and whose publish waits (`waiting`). It gives `false` for: a night `in_progress`; a night `queued`; a weekly `in_progress`; a dry run waiting at the run level with no jobs listed; another knock in progress; `total_count` over the page; a failed call (`gh` exiting 1); `now ≥ until`. `GC_NIGHT_JOBS` equals the `name:` of every job in any workflow with `group: gc-night` | a job name changed in one place only; a `waiting` run counted as busy (it would stop every knock while a night awaits approval); an unreadable list counted as quiet |
| H3 | `_knock_hours`: **the window matches `NIGHT_WINDOWS`** | Sweep 2026-11-02 to 2026-11-09 minute by minute with `GRANITE_CLOCK_UTC`. `knock_gate`'s clock part for `hourly` is true exactly where the check's own reading of `NIGHT_WINDOWS` and `START_MARGIN_MINUTES` says neither `t` nor `t+2 min` is blocked. For `night` it is true exactly on [08:00, 11:18). The two sets are disjoint. Then the check shifts the daily window an hour in a copy of `NIGHT_WINDOWS` (monkeypatched): the `hourly` set and `KNOCK_ANCHOR` follow. `knock.yml` has exactly two cron lines: `M * * * *` with M not 0, 17 or 30, and one daily line, the only one `keepalive`'s `if` names and the one `look`'s `if` excludes | the margin dropped; a copy of the hours instead of the definition; the anchor hard-coded; the modes overlapping; the cron at :00; `keepalive` on the hourly line |
| H4 | `_knock_settings`: **the ladder's numbers come from the settings** | Unset gives (48, 6, 16). `KNOCK_HOURLY_HOURS=24` gives a 6-hour gap at hour 25. `KNOCK_EVERY_HOURS=4` gives 4-hour rungs. `KNOCK_DAYS=10` makes it a person's at 240 h. `"5"`, `"48h"`, `" 48"`, `"-1"`, `"17"` (days) and `"7"` (every) each make `whose()` `"person"` with a why naming the variable. AST: no numeric literal 24, 48, 6, 16 or 384 in `knock_due`, `whose`, `knock_schedule` or `knock_gate` (only `knock_settings` holds the defaults). The three workflows carry the five lines (C16) | a number hard-coded; a workflow missing a line; an invalid value read as the default |
| H5 | `_knock_ladder` (replaces C2): **the cap, and the counts** | Drive the ladder from `since` = 1793262435 (29 Oct 08:27:15) with every knock failing: hourly calls at :47, night calls at 08:23:40, as `hourly_ladder_sim.py` does but through `refusal`'s own functions. 94 knocks (38 + 56), at most 19 per UTC day in 48 h, 4 after. Never two in one rung; gaps ≥ 30 min / 3 h; no hourly one in a window; none at or after `since` + 384 h (**the cap**); the last at 383.9 h. A `Retry-After` of 50 h pushes the next past it. A `"claimed"` entry 14 min old blocks; one 16 min old makes it a person's | the cap removed or off by a day; the rung or gap rule removed (counts rise); `Retry-After` ignored; the claim rule removed |
| H6 | `_the_knock` (C5 as amended): **no retry, no redirect** | Exactly one opener call in every case, a drop and a timeout included. `knock()`'s AST has one call of the opener and none inside a loop, a `try` that calls again, or `while`. `_no_redirect_opener()`'s handlers include no `HTTPRedirectHandler` subclass. A 301, 302, 303, 307 and 308 each give one call and exit 2. `knock.yml`'s knock step runs the child once: no `for`, `foreach`, `while`, `Start-Sleep` or second invocation | a retry loop; a redirect handler; a second invocation in the workflow |
| H7 | `_knock_claim` | `--knock-claim` writes one `"claimed"` entry only when the gate passes at `now` and at `now + CLAIM_SLACK_MINUTES`. In the same run (same run id and attempt) the child's gate passes over its own claim and makes one request; a different run id with the same claim 1 min old refuses with 4. The child turns the claim into the knock's entry (one entry, not two). `knock.yml`'s knock step's `if` is `steps.claimsent.outcome == 'success'` and the claim-send step's `if` is the claim's output. **The red team's two cases:** (a) `since` at 14:50:10 and the last knock at 13:52 two days on: a claim at 14:50:00 is refused, and so is one at 14:45:30 (five minutes on is past the switch, in the six-hour rung of the 13:52 knock); one at 14:45:00 is allowed (five minutes on is still before the switch), and so is its child seconds later. (b) A claim at 07:22:59 is allowed and one at 07:23:01 refused (07:23:01 + 7 min reaches the 07:30 margin). **The unclaim:** a claim followed by a child that exits 4 (its clock forced past 07:28 with `GRANITE_CLOCK_UTC`), by one whose lock is held, and by one that raises before `knocking()`, each leaves, after `--knock-unclaim`, one entry reading `"not asked"`; `whose()` stays `"night"`, `person_line()` is empty, and a different run's next look 16 minutes later pings nothing. A child killed after `knocking()` leaves `"no answer"`, which `--knock-unclaim` does not touch | the knock step runs without the claim reaching R2; two entries per knock; a run blocked by its own claim; the slack dropped (case a or b claims); the unclaim rewriting a `"no answer"` entry, or another run's entry |
| H8 | `_workflows_knock` | The shape of §3.1. Triggers `schedule` (the two cron lines of H3) and `workflow_dispatch`. The top-level `DRY_RUN` is the weekly's line. The knock job runs on `windows-2022` with `timeout-minutes` equal to `refusal.KNOCK_JOB_MINUTES` and its knock step at most 3. **Secrets:** `look` names `R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_READ_ACCESS_KEY_ID` and `R2_READ_SECRET_ACCESS_KEY` in its one state-down step, and never `secrets.R2_ACCESS_KEY_ID` or `secrets.R2_SECRET_ACCESS_KEY`; the knock job names the four write secrets only in its state steps; `HEALTHCHECKS_PERSON_URL` only in the ping steps; none other. **Permissions:** `actions: write` only in `keepalive`, whose `if` is the daily line alone. **Packages:** every `pip install` in `knock.yml` is `--require-hashes -r requirements-r2.txt`; every line of that file is `name==version` with at least one `--hash=sha256:`; its boto3 equals `requirements.txt`'s and `nightly.yml:682`'s. `--knock-look --help` runs in a temp tree holding only the sparse paths | a secret named that should not be; the write keys in `look`; `keepalive` minting its token hourly; an unpinned or unhashed install; the timeouts drifting apart; a sparse path missing |
| H9 | `_workflows_person_pings` | Every step that names `HEALTHCHECKS_PERSON_URL`, in any workflow, is evaluated for every run in `WF_RUNS`, as `_workflows_healthchecks` does. It pings for no dry run, and has the exact-ref guard before its `curl` (pwsh `HC_REF_GUARD`, or the bash form `if [ "$GITHUB_REF" != "refs/heads/main" ]; then`). In `knock.yml` it sends only `/fail` with `logs/alert-person.txt`, never a plain ping. In `nightly.yml` it sends C16's three cases | a plain ping from `knock.yml`; a ping for a dry run; the guard after the curl |
| H10 | `_knocks_on_file` (the log reader of design_final §6, moved to the state file). A data check beside `_nightly_log_findings` (dev `81750`), not in `--code`, skipped where no `archive/knocks.json` is on disk | In `current` and every `lifted[].knocks`: at most one per rung, gaps as above, no `hourly` entry inside a window, none at or after `since` + `KNOCK_DAYS`, none with a dry ref, no `"claimed"` older than a day. **And no `hourly` entry for a record before its settle time** (an `hourly` entry whose `epoch` is earlier than `last_window_end` after the record's own `epoch` + `KNOCK_SETTLE_MINUTES`) | — (it reads what happened; design_final §11's signs, made a check) |
| H11 | `_knock_settles`: **no hourly knock beside a laptop that may ask** (the red team's first finding) | With `GRANITE_CLOCK_UTC` and a record of kind `dropped`: noted 14:35 on a Thursday, the `hourly` gate refuses at 15:47, 23:47 and 06:47 and allows at 13:47 the next day; the `night` gate allows at 08:23 the next morning. Noted 12:29: allowed at 13:47 the same day. Noted 12:31: refused until 13:47 the next day. A relapse record noted 14:35 with a carried `since` two days earlier is judged by its own 14:35. **The property, swept:** for every record epoch E in a week (five-minute steps) and every minute t at which the `hourly` gate allows, `last_window_end(t) ≥ E + KNOCK_SETTLE_MINUTES`; and a stood-down laptop whose fake pull read is just before E + 60 min gets `gc_turn(t) == "pull"`. So any laptop `gc_turn(t)` lets ask pulled after the record could have reached the bucket | the rule dropped; `since` used instead of the record's `epoch`; the margin set to 0; the rule applied to the `night` mode |
| H12 | `_knock_silent` (the red team's fifth finding) | `hourly_silent()`: a record in its hourly phase, due since 13:30, with no `by: "hourly"` entry in the 18 hours before 07:30, gives the sentence; one `"not asked"` hourly entry at 02:47 gives none; a record noted 14:35 (held by the settle rule) gives none; a `Retry-After` reaching to 01:00 gives none (six open hours); a person's record gives none. Through `--runner` and `--close` on fakes: the first such night has it in `alarms()`, the night is not clean, and `warning_reasons()` is `[]`; the second night has it only in `warns_of()`, and the night is clean | the alarm every night (the check stays down); the alarm on the third check; no sentence at all; the night held by it |

**Left alone and still green:**
- `_night_clock` (C12: the gated list is unchanged, since the hourly caller is not `nightly.py`'s);
- `_knock_export_minutes` (C13);
- `_every_fetcher_checks_refusal`, `_every_fetcher_notes_refusal`;
- `_nightly_guards`, `_nightly_runner` 108;
- `_lane_daily`, `_night_window`.

---

## 9. Documents, and the CLAUDE.md wording

**The documents.** These are additions to design_final §7's table. Each changes in the commit that changes the behaviour it describes.

| Document | Change |
|---|---|
| `README.md` 344-353 | "GitHub asks one small file once an hour for two days, then every six hours, while the night tests a refusal" |
| `ARCHITECTURE.md` 140-150 | `knock.yml` among the workflows: what it does, its three jobs, that it pings no `HEALTHCHECKS_URL` |
| `ARCHITECTURE.md` 262-284 | The third check's two pingers, and why `knock.yml` sends only `/fail` |
| `CONTRIBUTING.md` 24-31 | One sentence on `knock.yml` |
| `SECURITY.md` 93-98 | `knock.yml`'s look job holds only a read-only R2 key; its knock job holds the write keys and the third check's URL, on at most 19 runs a day; both install boto3 by hash; its token lists Actions runs, and once a day re-enables the workflow; no re-run reaches the knock; nothing a stranger does starts it |
| `watchers/README.md` 71-83 | A lift can come at any hour outside 07:30–13:30 UTC; pull's line; the lane still stops; `refusal.py --clear` now makes the next fetch pull first; netcheck refuses while GitHub may test the copy here |
| `workers/night-timer/README.md` | One line: it starts the night only. Dispatching `knock.yml` from it is a possible later step if GitHub's hourly cron proves unreliable (§11) |
| `.github/workflows/nightly.yml` 129-139 and `weekly.yml` 56-67 | The "still open" note names the knock job as a third kind of holder, and points to `knock.yml`'s quiet job |
| the operator checklist (on the laptop) | D5 as in §6.2; the three variables; the knock workflow's off switch |

**CLAUDE.md is the owner's file.** Proposed replacement for design_final §7's paragraph (CLAUDE.md:74-79):

> **A refusal outlives the run that met it.** `refusal.py` records one in
> `archive/refused.json`, with what kind it was. It exists because a drain that
> met two 403s stopped itself correctly, and a chained run started asking the
> same address for a docket fifty-four seconds later. The lane, and GitHub's
> night, stop at a refusal for as long as it is on file; a fetch started by hand
> here stops for 24 hours, and for as long as it is on file if GitHub's night
> met it. One kind is the night's to test, by the person's decision of <date>:
> two dropped connections, timeouts, or a 503 that is not the firewall's page,
> met by GitHub's night on `main`. That night ends as before. For up to sixteen
> days the nights after build from the General Court's database, and GitHub
> asks the website one request at a time, for `dynamicdatadump/Counties.txt`:
> once an hour for the first two days and every six hours after (the repository
> variables `KNOCK_HOURLY_HOURS`, `KNOCK_EVERY_HOURS` and `KNOCK_DAYS`), from
> `.github/workflows/knock.yml` outside the night's window and once from the
> night itself at its start -- never two in one hour or span, never beside a
> night, a weekly or a dry run. Any answer that is the file lifts it (moved into
> `archive/knocks.json`); the full fetch waits for the next night, and for a
> week after, one dropped connection ends the export. Everything else -- a 403,
> a 429, the firewall's page or a redirect, on a night or to that request;
> sixteen days; a fourth relapse; a knock whose answer never reached the
> bucket; any refusal met on this laptop or by a dry run; any record from
> before <date> -- is a person's to clear, as it always was, and stops the
> database too: `python3 src/ops/cloud.py clear-refusal` for the night's and
> `python3 refusal.py --clear` here, after `netcheck.py` has said what kind of
> refusal it was. While GitHub may be testing one, set the variable
> `NIGHT_KNOCK` to `off` (or disable `knock.yml`) **before** netcheck or an
> early clear, so that two machines never ask at once; netcheck refuses on the
> laptop until told so (`--knock-stopped`), and `--clear` here makes the next
> fetch pull the bucket first. The Healthchecks check
> `HEALTHCHECKS_PERSON_URL` emails the moment a refusal becomes a person's, and
> nothing tests a refusal by itself unless that check is set and the repository
> variable `NIGHT_KNOCK` is `on`. Starting `knock.yml` by hand asks the General
> Court too, and is a person's to do.

**CLAUDE.md:92-98's added sentence** (design_final §7) stands.

**CLAUDE.md's "Branches, the nightly and the kit" gains:**

> `knock.yml` runs every hour and does nothing unless the bucket holds a
> refusal the night is testing; then it asks the General Court one small file
> at most (see *A refusal outlives the run that met it*).

---

## 10. Landing, and the build plan, amended

### Landing (design_final §8)

**Steps 1–4 stand.**

**Step 5 gains a dispatch of `knock.yml` on `dev`.** It is a dry run by its branch, and waits in `knock-dry-runs`, not `dry-runs`. Its log must show:
- `pip` installing from `requirements-r2.txt` with `--require-hashes` in `look` (Linux). A dry run never runs the knock job, so its Windows install is first run on `main`. The builder proves it beforehand: `pip download --only-binary=:all: --platform win_amd64 --python-version 3.14 --require-hashes -r requirements-r2.txt` on the laptop (PyPI, not the General Court). If it still failed on `main`, the knock job would fail before its claim: a red run, no request;
- `look` reading the bucket **with the read-only key**, and saying whose the record is (or that none is on file) and the settings in force;
- `NIGHT_PERSON_CHECK set`, once D5 is done;
- `quiet` and `knock` skipped;
- `state/` in the bucket unchanged: a listing before and after.

It cannot exercise a knock, by design.

**Step 6 (D5) stands, before the merge to `main`, with its step 8, the read-only key.**

**Step 7.** After the merge, `knock.yml` starts at the next :47. With nothing on file, each run ends after its look. The Actions tab gains about 25 green runs a day (24 hourly, one keepalive), the noise the owner should expect.

### Build plan (design_final §9)

Each commit still bumps stamps, passes `preflight.py --code`, carries its own docs and leaves the night safe as the last commit.

1. **The record says what it was.** Unchanged.
2. **The ladder and the knock's state (amended).**
   - `knock_settings()` and its validation; `KNOCK_ANCHOR` from `NIGHT_WINDOWS`;
   - the rung rule in `knock_due()`; `knock_schedule()`'s pattern; `whose()` condition 6 as in §1.4;
   - `RELAPSES_MOST` and `current.relapses`; the `"claimed"` entries and the stuck-claim rule; `by` and `attempt` in each entry;
   - `knocks.json`, `knocking()` / `knocked()`, the lift on disk, `drops_allowed()` and its two readers, `force()` and `main()` status, as before;
   - H4 (its `refusal.py` half), H5, C2b as amended, C4.
   - Inert.
3. **The bucket knows a lift (amended).** As before, plus §7's three orders (pull reads `refused.json` then `knocks.json`; send checks, reads, then puts; a lifted sha is absent to GitHub and moved by `state_up`). C8 and C9 with the new cases.
4. **The knock child (amended).**
   - `knock_gate(by)` with its two modes, the `hourly` mode's settle rule included; exit 4 for "not now"; the child's own 120-second kill; reuse of a claimed entry;
   - `refusal.py --knock-look`, `--knock-claim` (with `CLAIM_SLACK_MINUTES`), `--knock-unclaim`, `--person-line` / `--person-file`;
   - C5 as amended (H6), H3, H7, H11.
   - Nothing calls it yet.
5. **The third check and the switch (amended).**
   - The five env lines in `nightly.yml` and `weekly.yml`;
   - `_workflows_secrets`'s one allowed expression (§8.1); `WORKFLOW_SECRETS`;
   - `person_line()` shared with `person_alerts_of()`; the Healthchecks step's third ping;
   - C16, C11 (switch-off and invalid-setting cases), H4 (its workflow half).
6. **The night knocks (amended).** `GRANITE_KNOCK_BY=night` in `knock()`'s child; rc 4; the pattern sentences; the day-0 laptop sentence of §7; C6, C11, C12, C13, C18 sequences 1 and 3, as amended.
7. **The database while held** (D3). Unchanged but for the sentences. C18 sequence 2 as amended.
8. **New: the hourly knock.**
   - **First, before it:** the laptop's half of §7 (commits 9 and 10 below) lands before or with this one, so that no build of `main` has hourly knocks without the laptop's two rules.
   - `.github/workflows/knock.yml` (§3), with `requirements-r2.txt`; `WF_RUNS`; `_workflows_permissions`' message; `_workflows_dry_runs_wait` as amended (§8.2); `WORKFLOW_SECRETS`' two read-only names;
   - `refusal.hourly_silent()` and the night's alarm (§6.1);
   - H1, H2, H8, H9, H12, C18 sequences 4 and 5;
   - the `nightly.yml` and `weekly.yml` "still open" notes.
   - Safe as the last commit: it adds a second caller of the gated child, and nothing more.
9. **The laptop tightening** (was 8). design_final's `check()` at any age, plus `--clear` making the next fetch pull first (§7, item 2); C10 as amended. **Moved before commit 8.**
10. **netcheck** (was 9). Its verdict, as design_final, plus `gc_turn()` and the `--knock-stopped` refusal on a stood-down laptop (§7, item 3); C15 as amended. **Moved before commit 8.**
11. **Docs and the log reader** (was 10). As amended in §9. H10 replaces the log-line reader. The CLAUDE.md text goes to the owner.
12. **The guard rows (D6)** (was 11). **Amended** (the red team's second finding).
    - The guard already asks before an edit under `.github/workflows`, `gh workflow run`, and `gh variable` / `gh secret` (`.claude/hooks/guard.py:229-233`, `:328-329`), and before running `snapshot_gencourt.py` (`:64-66`).
    - **It does not ask before `gh run rerun`**, checked offline with its `decide()`: `gh run rerun 123 --failed`, `--job 456` and a bare rerun all return allow. `run_attempt` makes a re-run harmless to `gc-night` (§3.1), so this row is defence in depth: the guard asks before `gh run rerun`. The same check returns allow for `gh run cancel`, which can cancel a waiting night; asking before it too is listed for the owner. Both are configuration, the owner's (D6); C17 gains the two cases.

**Effort, a guess:**
- about 250 more lines of code and YAML, and about 500 more of preflight;
- about one more working day.

---

## 11. Risks and signs, added to design_final §10 and §11

**Risks:**
1. **The cost at a blocked address rises from 6 to at most 96 single requests over 16 days, with the default settings.** It is about 19 a day for two days, then 4 a day. The settings can raise it: `KNOCK_EVERY_HOURS=4` gives 120 knocks a chain, hourly throughout (`KNOCK_HOURLY_HOURS=384`) 298 (§2). This is the owner's trade for clearing a record within the hour of the website answering. What it buys the site is narrower than that sentence: the full fetch waits for a morning either way, and the night knocks at its start, so an hourly lift changes a morning only when the night starts after 11:18 UTC (§14, finding 5).
   - *Guess:* whether a firewall's ban lengthens on contact (design_final §15). If it does, hourly contact is the case that would show it.
   - Each request is 195 bytes, our User-Agent, never retried, no redirect followed.
2. **GitHub's scheduler** ran nights 5–7 h late in October. The hourly cron is best effort: late runs make it gentler, never denser (§2), and the 16 days are wall-clock.
   - A later option: the night-timer Worker could also dispatch `knock.yml` hourly. The knock would still go out from GitHub's runner, but it is a second dispatcher to maintain. Not in this branch.
3. **The race** (§5): bounded, not closed.
4. **The noise.** About 25 runs a day on the Actions tab (24 hourly, one keepalive), and about 24 bucket reads a day, with a read-only key. Public-repository minutes are free (*guess* that this stays so for `windows-2022` when the knock job runs).
5. **Windows and Linux runners may draw on different address pools** (*guess*). The knock job uses the night's image so that, if they do, it draws on the night's.
6. **A setting typed wrong turns the method off, and emails.** That is the safe direction, at the cost of an email.
7. **The laptop beside an hourly knock** (§7). Closed by the settle rule on GitHub's side and two rules on the laptop's, except for a drop night whose record took more than an hour to reach the bucket (both uploads late; §4.2), and a person who passes `--knock-stopped` without stopping the knock. The second is a person's word against their own instruction.

**Signs** (design_final §11, changed rows):

| Sign | Where | Meaning, and what to do |
|---|---|---|
| Two knocks in one rung, or closer than 30 min / 3 h | `state/knocks.json`; H10 | The ladder failed. Set `NIGHT_KNOCK` to `off` |
| An `hourly` knock inside 07:30–13:30 UTC, or a Monday's 03:30–06:30 | the same | The hourly gate failed. `off` |
| A `knock` job running while a night, weekly or dry run ran or waited | the Actions tab | The quiet job failed. Disable `knock.yml` |
| A `"claimed"` entry left in the bucket | `state/knocks.json` | R2 failed after a claim. The record is a person's (the third check emailed); read the knock run's log before clearing |
| A real night cancelled while a knock job held `gc-night` | the night's dead-man's switch | §5's residual. If it recurs, consider the lease (§5) |
| The night's alarm "the hourly knock has not run since …" | the night's check emails once; the run page | Disabled, paused by GitHub, no read-only key, or GitHub's scheduler down. Only the night's knock runs meanwhile, which is safe. Re-enable `knock.yml`, or add the key, or leave it if that was meant |
| `knock.yml` absent from the Actions tab's recent runs | the Actions tab | The same, seen by hand |
| An `hourly` knock for a record before its settle time | `state/knocks.json`; H10 | The settle rule failed; the laptop may have asked beside it. `off`, and read the laptop's logs |
| Many `"not asked"` hourly entries | `state/knocks.json` | Claims the child declined: a knock job waiting long for a runner, or a clock or rung rule out of step. Harmless; read why |

---

## 12. Guesses, added to design_final §15

- How many seconds lie between `quiet`'s last answer and the knock job entering `gc-night`.
- That GitHub keeps listing a run waiting at the run level with no jobs, which the quiet job reads as busy in any case.
- The look job's half minute.
- The knock job holding `gc-night` 3–5 minutes.
- `GITHUB_TOKEN`'s hourly API allowance.
- That Windows and Linux runners differ in address pool.
- That free minutes cover the knock job.
- Every number in the three settings. The owner chose 48 h and 6 h; neither is measured against gc.nh.gov.
- `KNOCK_SETTLE_MINUTES = 60`: a margin over the minutes a drop night runs after its record, not a measurement (§4.2).
- `HOURLY_SILENT_HOURS = 10`: that GitHub's scheduler stays under about 7 h late (§6.1).
- That a re-run reuses the first attempt's `quiet=true` (the sentence quoted for it was not found on the pages read); `run_attempt` makes the answer not matter (§5).
- That `queue: max` works on a job-level group (§5).
- That Cloudflare offers a bucket-scoped read-only R2 token under the names in §6.2, and that `make_bucket()` writes nothing when it opens R2.
- That boto3's six dependencies are all pure-Python wheels, so one hash file serves Windows and Linux (§3.2).
- That GitHub evaluates the workflow `env`'s `vars.` once per job (§1.6).

## 13. Corrections to design_final found while writing this

1. **§2.11 and C16 against `_workflows_secrets`.** The workflow-level `NIGHT_PERSON_CHECK` expression is rejected by `_workflows_secrets`' regex (nc `93403`). The check must be amended (§8.1).
2. **§2.4 and C5's "exit 2" for a refusal by the gate.** It is indistinguishable from "a person's". It is now 4 (§4.3).
3. **§2.6's "about 1 KB" per `lifted` entry.** It is now up to about 25 KB (§4.1).
4. **design_final §2.9's day-0 sentence** "the laptop's next pull will ask for `python3 refusal.py --clear` there" (`:327`; C11, `:556`) invited a laptop clear while GitHub tests the record. It now says nothing is needed on the laptop, and to set `NIGHT_KNOCK` to `off` first for an early clear (§7, item 4).
5. **design_final §4's "netcheck, then clear"** (`:432`) needs "set `NIGHT_KNOCK` to `off` first" whenever the record is one GitHub tests (§7, item 4).

---

## 14. Red team

The safety red team (`red/hourly_red_team.md`) made seven findings. Each was checked against the code at night-clock `22d19e4` (extracted to `red/nc_*.py` and `red/nc/`) before it was taken. Four hold as stated (1, 2, 4, 6). Three hold with one point corrected: a detail of 3, the consequence claimed in 5, and the Eastern hours in 7. None is rejected, and every one changed the design.

| # | Finding | Checked | What changed, and where |
|---|---|---|---|
| 1 (high) | The laptop and the hourly knock can ask at once | **Holds.** (i) The export is not clock-gated: nc `nightly.py:1649-1656` runs the snapshot at any hour; `asking_left`'s callers are nc `3994`, `4087` and the knock. GitHub's fallback started nights at 12:42–15:38 UTC (read_holds `:34`, `:133`). (ii) `refusal.py --clear` unlinks `MARK` and leaves the pull's read (`refusal.py:839-859`); `gc_turn` then passes (`:707-744`, `refusal_read` `:678-692`). The pull's line is quoted short: it reads "lifting only this one brings it back at the next pull" (`cloud.py:2819-2821`), a warning, but nothing makes that pull come first. design_final's day-0 sentence does name the laptop's clear (`design_final.md:327`; C11 `:556`). (iii) netcheck imports nothing of `refusal` (`netcheck.py:45-57`), and design_final §4 sends the person to it (`:432`) | Taken, with three refinements. **The settle rule** (§4.2) judges the record's own `epoch`, not the chain's `since`, so a relapse a late night wrote is judged by its own time. **`--clear` writes `archive/refusal-cleared.json`** and `refusal_read()` reads it, rather than `refusal.py` editing `cloud.py`'s `pull.json` (§7, item 2). **netcheck also applies `gc_turn()`**, the laptop's existing one-fetch-at-a-time rule it alone skipped, besides the `--knock-stopped` refusal (§7, item 3). The person's word everywhere (§7, item 4; §9; for_owner). §7's wrong sentence is corrected in place. C10, C15, H10, H11. The cost to the site of the settle rule is nothing: `hourly_ladder_late.py` (§2) |
| 2 | A re-run of the knock job skips `quiet`, and the guard allows it | **Holds.** The guard's `decide()`, run offline on night-clock's `guard.py`, returns allow for `gh run rerun 123 --failed`, `--job 456` and a bare rerun, and ask for `gh workflow run`. GitHub's re-run page, read today, allows re-runs "up to 30 days after its initial run", with the same ref. **Not found:** the sentence quoted about successful jobs' outputs, on either re-run page read; so whether the old `quiet=true` is reused is a *guess*. The fix does not depend on it | `github.run_attempt == '1'` in the knock job's `if`, compared as a string (§3.1, §5 item 5); H1 holds it. The guard asks before `gh run rerun` (D6, §10 item 12). The same check found `gh run cancel` allowed; listed for the owner. **`queue: max`:** GitHub's page documents it with a workflow-level example only, and says nothing of job-level groups, so it stays a later option needing a dry-run proof (§5) |
| 3 | A claim the knock then declines becomes a false "a refusal is yours" | **Holds** for both cases (the phase switch; the 07:30 margin). **Wrong in one detail:** "the same happens if the owner changes `KNOCK_HOURLY_HOURS` mid-chain". The claim and the child are steps of one job and read one workflow `env` (*guess* that `vars.` is evaluated once for the job); a change between runs makes the next look's `go` false, not a claim and a declining child. The fix covers it either way | **The unclaim is a workflow step, not code in the child** (§1.6 rule 5, §3.1): `--knock-unclaim`, `always()`, after the knock step and before the state-up. So a crash, a held lock and the step's 3-minute kill before `knocking()` are covered too, which a rewrite inside the child would miss. Safe because `knocking()` writes first. **The claim's slack** (§1.6 rule 1): the gate at `now` and `now + 5 min`. H7 has both of the red team's cases, with corrected times |
| 4 | The bucket's write keys run in more jobs, more often | **Holds.** `look` held the four write secrets about 24 times a day; `requirements.txt` pins boto3 and none of its six dependencies (night-clock's `requirements.txt`); `keepalive` minted `actions: write` hourly to use it once. `nightly.yml:5-6` asks for the least permission each job needs | **A read-only R2 key** for `look`, two new repository secrets (§3.2, §6.2 step 8); without it the hourly knock stands down and the night says so. **`requirements-r2.txt`, hash-pinned**, for `look` and `knock` (§3.2). **`keepalive` on a daily cron line of its own** (§3.1). H8. Not in this branch: the same pinning for the night's, the weekly's and the publish job's installs (§15) |
| 5 (low) | Nothing tells the person when `knock.yml` stops | **Holds in part.** True: nothing said so. **Overstated:** "no email says why the site stays a day behind". Stopping `knock.yml` does not by itself leave the site behind. The full fetch comes only in a morning (no mid-day run, the brief), and the night knocks at its start whenever its rung allows (§4.3), so without the hourly knocks the same morning knock decides the same night. The site differs only when the night starts after 11:18 UTC and may not knock (`KNOCK_LATEST`), where an earlier hourly lift would have let it fetch (the export is not clock-gated, nc `1649-1656`); and on a Monday, when the weekly, which never knocks, asks its website pieces only if the record was lifted before 04:17. One case cuts the other way: an hourly lift in the evening followed by a morning drop makes a relapse night, which builds nothing (rule A), where a failed morning knock would have made a database night | Taken: `refusal.hourly_silent()` and one alarm through the night's own check on the first night of silence, then the held line (§6.1); H12. Not through the third check, whose email means "a refusal is yours". for_owner says what the hourly test buys and what it does not |
| 6 (low) | A knock dry run can cancel a waiting nightly or weekly dry run | **Holds.** `knock.yml` joined `dry-runs` (the earlier §3.1), where a newer run replaces the one waiting (nightly.yml `:143-145`; weekly.yml `:68-70`), and its knock job requires `main` | `knock-dry-runs` (§3.1, §3.2); `_workflows_dry_runs_wait` amended to require `dry-runs` only of a workflow whose `gc-night` job can run on a dry run (§8.2) |
| 7 (low) | The owner's numbers hold only at the defaults, and in summer time | **Holds**, with one correction. From 1 November the night's span 07:30–13:30 UTC is 2:30–8:30 a.m. EST. **Monday's quiet hours, 03:30–06:30 UTC, are Sunday 10:30 p.m. to Monday 1:30 a.m. EST**; the red team's "11:30 p.m. to 2:30 a.m." are the EDT hours. Daylight time changes nothing else: the windows, rungs, cron and timer are UTC (`refusal.py:520-526`; `workers/night-timer/wrangler.toml:10-11`) | for_owner gives the EST hours, Monday's, and "with the default settings; hourly throughout would be about 300" |

---

## 15. Open questions for the owner, added by this revision

1. **The read-only R2 key** (D5, step 8). Without it the hourly knock does not run; nothing is less safe.
2. **The guard rows** (D6): ask before `gh run rerun` and `gh run cancel`. Configuration, the owner's.
3. **Hash-pinned installs for the night, the weekly and the publish job**, as `knock.yml` now has. The same gap, once a day each, holding the same keys. A separate change.
4. **`queue: max` on `gc-night`**, later, after a dry-run proof. It would close §5's race, the re-run case and the night's own open case, and it changes the night's concurrency.
5. **What the hourly test buys, said whole** (§14, finding 5). With no mid-day run, an hourly lift changes a morning only when the night starts after 11:18 UTC, and Monday's weekly; one case (an evening lift, then a morning drop) makes a morning worse. A morning knock alone would cost at most 16 + 2 requests a chain, against 96. The owner chose hourly; this is said so that the trade is seen whole, not to reopen it.
