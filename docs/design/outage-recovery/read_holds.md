# Every hold that waits for a person

Read-only. Code read at `dev-ioxv9i` = `origin/dev` = 4590795. That is one commit past 0702100, and the extra commit touches only `src/pages/lang/es.json`. Also read: `origin/feat/night-clock` at 84a81ee, and `origin/main` = 6ab3380, the code that ran on 29 October.

Evidence used:
- the bucket's `state/` (last-night, last-weekly, last-dry-run, census, livestreams, refused);
- the main nights' logs from 30 September to 29 October;
- the 28 October `built-checks.json`;
- `inbox/laptop/` and its `replaced/` copies;
- a listing of `replaced/`, which the bucket keeps for 30 days (`cloud.py:66-67`);
- GitHub's run list for `nightly.yml` on main, and the jobs of run 38876245400.

Nothing was asked of the General Court, the SQL host or YouTube. Nothing was written to the bucket. **"Guess"** marks anything the code, the logs or the history do not show.

---

## 0. The ranked table

The ranking puts first the holds most likely to leave the site stale for days without a person. Each rank weighs three things: how likely the hold is to fire, how much of the site it stops, and whether it ends by itself.

| # | Hold | Trigger | What it stops | How a person lifts it | Fired (evidence) | Can it lift itself? |
|---|---|---|---|---|---|---|
| **1** | **The General Court refusal record**: `archive/refused.json`, carried as the bucket's `state/refused.json` | `snapshot_gencourt`: one 403/429/503, a block page or a `Retry-After`, **or two dropped connections**. `fetch_committees` (weekly) the same. `fetch_lsrs` / `--listing`: one 403 etc. | **The whole site.** On GitHub the night fetches nothing at any age of the record (`nightly.py:1233-1246`, `1541-1557`). That includes the database fallback (`3011-3015`), the study views, the term data, the bill requests, the statutes and the documents list (`1622-1653`). Nothing is installed, so nothing is built or published. The weekly also skips its SQL steps (`5981-5985`). The lane stops (`gc_lane.py:402-406`). Fetches started by hand stop for 24 h (`refusal.py:211-252`) | `python3 netcheck.py`, then `python3 src/ops/cloud.py clear-refusal` (bucket), and `python3 refusal.py --clear` on the laptop if pulled (`nightly.py:5761-5763`) | **Now.** 29 Oct, run 151, two `RemoteDisconnected`. It is the first on GitHub's machine: `replaced/` (30 days) holds no earlier `refused.json` and no clear. Two blocks happened in the laptop era (CLAUDE.md) | **Drops and timeouts: yes, if designed** (§1). **403, 429 and the block page: no** |
| **2** | **The new term** (`turned`, `roster`, `smaller`). It needs a **freeze** first | The export's files name a newer term, or carry a new House roster before the term's roster is frozen (`fetch_status`, `nightly.py:2780-2799`). Expected on Organization Day, **2 December 2026** (`nightly.py:2858`). Also the session year in January 2028, and the January committee wipe for the weekly | **The whole site.** Nothing is installed or built, every night (`plain_why` `2300-2316`) | On the laptop: pull, then `python3 src/lib/freeze_term.py --session` (and `--views`), then `cloud.py seed-kit`. Then run the nightly by hand on main with **New term** and **Take the day's data** ticked and **Dry run** unticked (`2170-2228`). Then **approve** in `production-review` (`nightly.yml:100-106`, `657`). The weekly New term run is separate, by hand | Never yet: the first turn under GitHub. **It is certain to fire, on a known date** | **No, by the owner's rule** of 30 Sep and 5 Oct (`nightly.py:2149-2173`; `nightly.yml:100-106`). The date is known, so the owner can be present for it |
| **3** | **The approval gate**: `production-review` | The publish waits for a reviewer when the gate holds (`nightly.py:786-822`). Its reasons: **a release** (tonight's commit is not production's, `838-843`), unless a clean dry run of the same commit closed within **48 h** (`4583-4603`); **far more changed** (more than 600 current-term rows against production's, any finished term's list differing, or production's lists unreadable, `872-878`, `4636-4686`); **a new warning kind** (not served, and not in a night published within 14 days, `4819-4844`); **a failed "hold"-tier check of the built site**, 97 of them on 28 Oct, or checks that did not run (`4775-4785`; `preflight.py:109729-109767`) | **The live site's update.** The night builds and the preview deploys. Production waits. **Every later night holds again while its reason stands**, because each reason is measured against production, which has not moved | Approve the newest waiting night in `production-review` (`nightly.py:5734-5736`). An older night's site is kept only 3 days (`nightly.yml:478-480`) | **5 of the 13 nights 16–28 Oct**: 16, 22, 24 and 25 (release) and 18 (finished terms rewritten). All were approved the same day. On 16 Oct the publish job waited 2 h 16 min (created 10:00:42, started 12:17:12). In shadow, 7–15 Oct, it would have held 3 of 9 nights | **Partly already:** the release reason lifts on a proven dry run (48 h). The rest is the owner's design of 6 and 12 Oct |
| **4** | **A failed workflow step fails the night job, so nothing publishes** | `livestreams.py` exits 3, "not set up": no key, **a refused key**, **a channel or uploads playlist 404**, or no yt-dlp (`livestreams.py:2010-2023`, `api_error` `830-859`); or it exits 1. Also a failed preview deploy (Cloudflare token), pack, or kit-up (R2). `--close` exits 1 on any failed step (`nightly.py:5842-5853`, `5887`). The publish job needs `needs.night.result == 'success'` (`nightly.yml:653`) | **The whole site's publish, every night until fixed.** The day's data is still taken and built, on purpose ("fails the night, loudly", `nightly.yml:389-394`) | Fix the secret or configuration: `YOUTUBE_API_KEY`, `CLOUDFLARE_API_TOKEN` or the R2 keys. A channel the General Court renames or removes needs a code change | **0** of the scheduled or timer nights since 8 Oct: run 151 is the only failed one in the run list, and it failed for the refusal | **A transient failure lifts the next night. A revoked key, an expired token or a vanished channel must be fixed by a person.** Whether a broken livestream step should *hold the publish* at all is worth putting to the owner (§3.4) |
| **5** | **The census gates and the file ceiling** | A build counting at least 2% fewer bills, legislators or bill_data, 5% fewer pages or feeds, or 1% fewer bills in a finished term, than `archive/census.json`; or 95,000 files or more (`nightly.py:516-518`, `1372-1402`) | **The whole site.** Not publishable (`5088`, `5196-5199`). The baseline is rewritten only on a night that passes (`5154-5157`), so **every later night is blocked against the same old counts** | GitHub never passes `--force` (`nightly.py:44-48`). Only a New term run lets a fall through, and never a finished term's fall or the ceiling (`1394-1402`). Otherwise a code or data fix. It is **not** self-lifting | **0**: "NOT FOR PRODUCTION" appears in none of the 29 main logs | **No.** A fall is the signal |
| **6** | **The database fallback stopped by its own checks** | Only while the export comes back empty. `dayfiles_from_db` guards stop the install (`DB_STOPPED_MOST = 2`, `nightly.py:1085-1097`) | **The whole site, for as long as the export stays empty.** "the same check stops the fallback every night until the export returns or a person decides" (`2449-2466`) | No command lifts it. The export returning lifts it, or a ceiling-type stop widens by itself (`stopped_next`). Otherwise a person reads `day_files.stops` and changes code or data | **0 stops.** Five database nights, on 3, 4, 5, 9 and 12 Oct, all installed. The DB fallback dates from 1 Oct (`e55795f`) | **Partly already** (ceilings widen) |
| **7** | **Late-caption check** and **tracked code changed** | More than 10, or more than 1%, of the recordings with published times not compared (`nightly.py:748-754`, `5100-5107`). A tracked code file differs on the runner (`5109-5111`) | **The whole site's publish** (`blocking`), each night while it stands | The late-caption check lifts itself once `caption_spans.json` covers the recordings. Tracked code: a code fix | **0** in the logs read | The late-caption check, yes. The tracked-code check, no |
| **8** | **The laptop's share** (`bill_text.json`, `amendments.json`, `committee_reports.json`, `calendars.json`, `journals.json`, `meetings.json`, `schedule_pages/_events.json`) | These move only when the laptop's fetches run and `seed-kit` sends them: "both a person's to start" (`nightly.py:3425-3441`, `3680-3703`) | **Part of the site**: bill-text search, House reports, calendars and journals, meetings. The night still publishes. A warning comes once the share is 7 days behind in session or 42 in the interim | Laptop fetches by hand or the lane, `extract_calendar_text.py` by hand (`watchers/README.md:147`), then `cloud.py seed-kit` (CLAUDE.md: ask first) | Not firing now (interim) | **Not as built.** `feat/night-documents` and `feat/night-handover` (unmerged, 26 Oct) move part of it to the night |
| **9** | **The weekly job's holds** | The refusal record. The January committee wipe ("kept smaller"). A step not taken | **Part of the site**: committee rosters, members who left, study committees, statutes. The weekly publishes nothing; the night builds from what it took | The refusal: as #1. The new term: the weekly New term run by hand (`nightly.py:2227-2246`) | The weekly was clean on 26 Oct (`state/last-weekly.json`) | "Kept smaller" asks again the next week by itself. The new term and a refusal do not |
| **10** | **Captions**: YouTube's bot check on GitHub's machine. The **captions inbox** relies on the laptop being on and logged on | Every caption ask from GitHub's machine has met "not a bot" since 26 Sep / 12 Oct (`livestreams.py:308-327`). The inbox job runs at 7:30 pm, "Run only when user is logged on" (`src/ops/README.md:46-66`). After 3 failures a recording becomes `for-laptop` (`livestreams.py:505-506`) | **Part of the site**: new recordings keep the schedule's *approximate* start. The night still publishes | Nothing for the bot check: its hold expires (12 → 24 → 48 → 96 → 168 h, `livestreams.py:510-515`). A different route is a person's decision (`:323-327`). `for-laptop` needs `--catch-up` on the laptop | GitHub's hold: count 7, until 2026-11-03 06:20 UTC (`state/livestreams.json`). The laptop ran every evening 18–28 Oct and sent 6–13 captions a run on 19–24 Oct. It has asked for nothing since 25 Oct, with 1 recording waiting, and the verdict's "inbox silent" warning has stood since 25 Oct | **Already self-expiring.** The laptop dependency is the real person-dependency |
| **11** | **The SQL host's own hold** (`archive/sql-held.json`) | A failed connection to PublicSQL (`probe_db.py:73-115`, `HOLD_HOURS = (20, 44, 92, 164)`) | Database pieces only (warnings). The fallback on an empty-export night. **Never the export's day files** (`nightly.py:393-403`) | Nothing: it expires. A *login-refused* hold re-arms weekly until the credentials in `probe_db.py` change, which is a code change (`probe_db.py:88-103`) | **0**: no `sql-held.json` in `state/` or in `replaced/` over 30 days | **Already self-expiring.** The approved precedent for #1 |
| **12** | **Starting the night**: the night-timer's GitHub token; GitHub's cron; the 60-day schedule disable | The fine-grained token expires ("a year", `workers/night-timer/README.md:22-25`). A 401 or 403 stops it at once (`index.js:74`, then it throws at `:77-78`). GitHub disables the scheduled workflow after 60 idle days (`nightly.yml:793-819`) | Not the site: GitHub's own cron runs the night late. It ran 5–7 h late on 19–24 Oct (runs created 12:42–15:38 UTC). With the night-clock branch, a late night still publishes, and its bill requests and documents list wait a day | Renew the token and run `wrangler secret put` (README). The keepalive re-enables the workflow itself | 0. The timer has run since 25 Oct | No for the token. Yes for the keepalive |
| **13** | **The laptop's own holds**: the lane; the morning pull; the stand-down; the refusal-unsent marker | The lane stops at **any** `refused.json`, any non-zero step, GitHub's window, or an empty queue for 12 h (`gc_lane.py:29-37`, `132`, `402-406`, `462-467`). No laptop General Court request starts until `cloud.py pull` has read the bucket since the last window (`refusal.py:707-744`). "reading the bucket is a person's command here" (`gc_lane.py:52-53`) | Laptop fetches only, which feed #8. Not the night | `cloud.py pull --changes-only`, then restart the lane (`watchers/README.md:79-83`) | Laptop logs are not in the bucket. Not known | Deliberately a person's (attended machine) |
| **14** | **The email sender** (`workers/follow`) | `PROBLEMS` (`sender.js:103-114`): Resend refuses the key or domain; tonight's changes file is still missing at noon | Email only: after noon it sends what it has (`sender.js:30-32`). Never the site | Renew the Resend key | Not visible from here | The missing changes file is self-lifting. A refused key is not |
| — | **The live layer, designed and not built** (`wf16/design_final.md`) | `control.json`, "a person only" (§ lines 422-434). ENCRYPT_REQ "§2.8 is the decision" (line 442) | Live pages only | `wrangler r2 object put …control.json` | n/a | Its own holds "each end by the next New Hampshire day" (line 436) |

**How the person learns of each hold.**
- The refusal, the SQL hold, a "hold"-tier check that failed, and a night that was not clean go to the night's Healthchecks check (`alerts_of`, `nightly.py:5750-5776`). It sends **one email when the check goes down and one when it comes back** (`5685-5690`).
- An approval wait, a failed check against the record, and "not moving" go to the warnings' check (`warns_of`, `5739-5747`), and only when `HEALTHCHECKS_WARN_URL` is set (`nightly.yml:597-613`).
- GitHub emails a required reviewer about a waiting deployment. That is from GitHub's own documentation, not this repository. So is the guess that a pending approval fails after 30 days.

---

## 1. Rank 1: the refusal record

**Trigger, as coded.** `refusal.classify` names the outcome (`refusal.py:269-307`): 403, 429, 503, any `Retry-After`, or the block page is **refused**; `RemoteDisconnected`, a reset, a timeout or `SSLEOF` is **dropped**. `snapshot_gencourt` counts the data page and the files together: one refused answer ends the run, and so does a second drop (sibling `read_refusal.md` §5). The record it writes has **no kind**: `{at, epoch, where, why}` (`refusal.py:113-127`). A drop and a 403 therefore look the same to every reader after it.

**Three readers, three rules** (`refusal.force`, `refusal.py:195-208`):
- a fetch started by hand: 24 h (`QUIET_HOURS`, `:105-106`, `:211-220`);
- the lane: any age (`gc_lane.py:402-406`);
- GitHub's night and weekly: any age (`nightly.py:26-30`, `1233-1246`, `5981-5985`).

**What it held on 29 Oct.** The verdict shows `fetch: refused`, `files_from: none`, `built: false`, `publishable: false`, `exit: 1`. Its alert reads: "Every fetch waits until a person clears it" (`state/last-night.json`). From then until someone runs `clear-refusal`, every night is deferred at `gc_quiet` and fails its job, the site stays at 28 Oct's build, and Healthchecks sends no further email (the check stays down).

**It also closes the door the IT office opened.** `gc_quiet` guards the whole asking block, so a web refusal also stops the study views, the term data and the statutes from PublicSQL (`nightly.py:1541`, `1622-1653`). It stops the database fallback too (`3011-3015`: "carrying on by another door is a person's decision"), and the weekly's SQL steps (`5981-5985`). That contradicts `probe_db.py:109-110`: "A refusal from the web server does not hold this host, and the reverse". It also runs against the IT office's "No problem hitting PublicSQL during a session".

**Can it lift itself? Yes for drops and timeouts, under these conditions:**
- the record learns its kind;
- the lift happens only on GitHub's machine;
- dry runs never lift;
- **at most one spaced knock a night**: a single GET with our own User-Agent, under the night's own lock, inside its asking window. It must never come from a second machine;
- the bucket records the lift, so `pull` and `send-refusal` do not put the refusal back (sibling §3, §9);
- the ladder is 20/44/92/164 h, following `probe_db`;
- **any** 403, 429 or block page on the knock makes the record a person's for good.

On **503** (a judgement; the code cannot settle it):
- treat it as resumable, on the longer ladder;
- never knock before both the `Retry-After` time and the next rung;
- a 503 on the knock counts as a failed knock, never as a lift;
- why: the firewall's block has always arrived as a 403 or as a 200 "Web Page Blocked / Attack ID" page (`refusal.py:265`), and the repository records no 503 from gc.nh.gov (sibling §11).

**429 stays a person's**: it is a rate complaint aimed at us. **403 and the block page stay a person's**, per the standing rule.

**netcheck's last line is not evidence a machine may use.** It counts a 403 or a block page as "got through" (sibling §2, `netcheck.py:162`, `196-198`).

---

## 2. Rank 2: the new term, which is certain

- **Date.** `new_term_ready`'s docstring gives the turn as "2026 on 2 December 2026" (`nightly.py:2858`).
- **What happens without a person.** On the first night the export names 2027, or seats a new House before the roster is frozen, `fetch_status` returns `turned` or `roster` (`2780-2799`). Nothing is installed, and the page says which boxes to tick (`2300-2316`). This repeats every night.
- **What the person must do, in order:**
  1. **freeze the term being left** on the laptop (`freeze_term.py --session`, and `--views` for `db/term/`), from the installed files, and send it with `seed-kit` (`NEW_TERM_TURN` `2170-2173`, `NEW_TERM_FREEZE` `2218-2223`);
  2. run the nightly by hand from main with the right boxes;
  3. approve it in `production-review`. It always waits (`REVIEW_NEW_TERM` `2157-2158`; `nightly.yml:100-106`).
- **Nothing it accepts is kept until that deploy lands** (`nightly.py:277-298`). A rejected or forgotten run leaves the next night refusing the same files again.
- **Further turns.** The weekly has its own New term run for the January committee wipe (`2227-2246`). The session-year turn of January 2028 is the shrink rule's "smaller" again (`2310-2316`).
- **Can it lift itself? No, by the owner's decisions** (30 Sep, 5 Oct). The date is known, so this is the one hold that can be planned for.
  - Guess: the freeze could be prepared by the night itself before 2 December, which would leave only "tick the box, approve" for the person. That would be a design change needing the owner's OK.

---

## 3. Ranks 3 and 4: the publish, which an auto-resume must not forget

### 3.1 The gate holds every night after, not just the first
Each reason compares tonight with **what production serves** (`size_reasons` reads production's bill lists, `nightly.py:4636-4686`; `release_reasons` reads production's `build.json`, `4606-4616`; `warning_reasons` reads the served kinds and the last 14 days, `4819-4844`). A held night that nobody approves changes nothing in production, so the next night is measured against the same thing and holds again.

### 3.2 Three ways a fetch that resumes by itself could still end in a person's approval
1. **The release proof expires.** A release is let through only by the newest dry run of the same commit, built, clean, and closed within 48 h (`4583-4603`). If a release is merged and an outage then lasts more than 48 h past its dry run, the first night back waits for approval.
   - This matters now. The 1 November release and the night-clock merge in early November are both releases.
2. **An outage in session trips the size reason.** "579 over its busiest three days running ... is what a night after two failed ones would carry" (`863-871`). Three or more session days missed could exceed `REVIEW_ROWS_MOST = 600` against production. That night would hold, and so would each night after it until someone approves.
   - In the interim, nights move 35 bills at most (`863-864`), so a few days' outage now would not trip it.
3. **A new warning kind.** A warning that first appears after the outage holds if its kind is not "the record not moving" or one of the fallback's (those are exempt, `4834-4836`).

**Implication for the design:** an automatic lift of the refusal restores *fetching*. Whether the *site* updates still depends on these three reasons. In session, either a bounded exemption for "the first night after a self-lifted outage", or an approval, is needed. That is a decision for the owner, not shown by the code.

### 3.3 Retention limits
- A held night's site is deleted after **3 days** (`nightly.yml:478-480`; `nightly.py:5736`).
- An older night is refused once a newer one is fit (`newer_fit`, `5524-5545`, `5593-5603`). So "approve the newest" always works, but a backlog cannot be approved in order.

### 3.4 A failed step blocks the publish
The livestream step is `continue-on-error`, but `--close` reads its *outcome* and exits 1 (`nightly.py:5842-5853`, `5887`), and the publish job needs the night's job to succeed (`nightly.yml:653`).
- So a YouTube key Google refuses, or a channel the API cannot find (`livestreams.py:848-858`, exit 3), **stops every publish** until a person fixes it, even though YouTube refusing *captions* explicitly does not (`livestreams.py:308-321`).
- The same holds for a preview deploy that fails because the Cloudflare token expired. The token's expiry is not recorded anywhere in this repository: **guess**.
- A question worth putting to the owner: should a broken livestream step or preview warn and still let production go? Today the workflow's comment says it is meant to fail "loudly" (`nightly.yml:389-394`).

---

## 4. What fired, in numbers

| Hold | Nights it fired | Source |
|---|---|---|
| GC refusal | 1 (29 Oct) | `state/refused.json`; no `refused.json` under `replaced/` (30 days) |
| Approval gate (on, from 16 Oct) | 5 of 13 (16, 18, 22, 24, 25 Oct), approved same day | night logs' "the gate:" line; run list; run 38876245400's jobs |
| Approval gate (shadow, 7–15 Oct) | would have held 3 of 9 (7, 8, 14 Oct) | night logs |
| Export empty, night not clean | 2 (1, 2 Oct) | night logs |
| Database night (installed) | 5 (3, 4, 5, 9, 12 Oct) | night logs |
| DB stop, census block, late captions, tracked code | 0 | night logs ("NOT FOR PRODUCTION" absent) |
| SQL host hold | 0 | no `sql-held.json` in `state/` or `replaced/` |
| Failed night job (scheduled or timer) | 1 (29 Oct) of runs 30–151 on main | GitHub run list |
| GitHub cron late | 6 nights, 19–24 Oct, 5–7 h | runs 96–116 created 12:42–15:38 UTC |
| YouTube bot check on GitHub | every ask since 26 Sep (code comment); hold count 7 | `livestreams.py:315-317`; `state/livestreams.json` |
| Captions inbox silent | since 25 Oct (4 days on 29 Oct) | verdict `not_moving`; `inbox/laptop/*.json` |

---

## 5. Where the owner's idea helps these holds, and where it cannot

- **It cannot lift rank 1**, for two reasons:
  - the live Worker reads PublicSQL and "never gc.nh.gov" (`design_final.md` §0, §6.1);
  - a knock from Cloudflare's network, like netcheck's from a cloud container, says nothing about GitHub's runner. It would also be a **second machine asking** beside the night, which is how the second block happened (CLAUDE.md).

  The knock belongs inside the night's job, under its lock.
- **It does help:**
  - **(a) Evidence for "outage, not block".** From January to June its heartbeat shows the General Court's *database* answering (`design_final.md:345`).
  - **(b) Rank 1 becomes much less costly if the database is the night's source while a *dropped*-kind record stands.** That needs `gc_quiet` to stop holding the SQL steps (`1541`), `from_database` to stop refusing (`3011-3015`), and the loop's "only after empty" (`1587-1589`) to change. It also needs the owner's OK. The IT office's email supports it, and `probe_db.py:109-110` already says the two hosts do not hold each other.
  - **(c) Readers keep seeing current information while the night is held.** Live Now and the live votes keep the visible parts current.
  - **(d) The Worker's expiring holds (`design_final.md:436-445`) are the same pattern as `probe_db`'s.**

---

## 6. Discrepancies found while reading
- **`nightly.yml:100-106` contradicts the gate's own comment.** It says "Today the 'production' environment has [the person] as its required reviewer for every deploy". The gate's comment says "production, which has no reviewer" (`nightly.yml:620-623`; `nightly.py:815-819`). The real settings could not be read: the session's GitHub token was refused. Which is true decides whether *every* night waits.
- **`refusal.py --clear`'s plain status line** says a record "older than 24h ... no longer stops anything" (`refusal.py:861-863`). That is false for the night and the lane.
- **`cloud_kit.json`'s `last-dry-run.json` says "No night reads it".** `proven_by_dry_run` reads it (`nightly.py:4586-4603`).
- **CLAUDE.md says the lane is held "for 24 hours"**; the lane holds at any age (`gc_lane.py:33-37`).

## 7. Guesses, stated as such
- A GitHub-hosted runner's egress address differs from night to night. Nothing here records it.
- The Cloudflare, R2, YouTube and Resend credentials' expiry dates are not in the repository.
- GitHub fails a deployment waiting for approval after 30 days. That is from GitHub's documentation, not checked here.
- GitHub will at some point retire the `windows-2022` image both jobs use. If so, the jobs would stop starting until a person edits the workflow.
- The 1 waiting recording that has kept the inbox "silent" since 25 Oct is probably waiting on its retry schedule (`RETRY_DAYS`), not a broken laptop. The laptop's record shows it ran and asked for nothing.
- Eight "hold"-tier night checks read today's date (`_session_chips_seat_of_their_term`, `_committee_rosters_current`, `_study_committees_built`, `_hearing_is_the_bills_own`, `_print_sheet_on_the_record`, `_every_rollcall_on_its_sitting`, `_past_sponsors_filled_data`, `_header_mark`). Any of them could start failing at the term's turn and hold every night for approval. Not tested.
