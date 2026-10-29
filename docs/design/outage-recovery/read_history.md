# How often the General Court's web server has dropped, refused or blocked us, and for how long

Read-only. No request went to gc.nh.gov, gencourt, the SQL host or YouTube. Nothing tracked was edited.

**Sources**
- **The bucket.** Every log under `logs/`: 140 files, 30 Sep to 29 Oct 2026. That covers the nightly, the weekly, dry runs, the earlier copies of a day kept as `*.log~HHMMSS`, and the YouTube logs. Also `state/{refused,last-night,last-weekly,last-dry-run,census,livestreams}.json`, and the laptop backup's `backup/archive/queue.csv`, the calendar drain's queue with a time on every row. All downloads have been deleted.
- **The repository** at `dev-ioxv9i` (`4590795`), plus `origin/feat/night-clock` (`84a81ee`). Its git history **starts on 17 Sep 2026** (`4bbe30d`), so everything before that comes from comments, version stamps and `HANDOFF.md` as it stood in `4bbe30d` and up to `84d51eb^`.
- **Times.** Logs and `refused.json` are written in Eastern time: the runner's clock is set to Eastern, and `refused.json` has `"at": "2026-10-29T04:27:14"` with an epoch that is 08:27:15 UTC. Below, times are in UTC with EDT beside them where it helps.

---

## 1. The short answer

1. **Two firewall blocks are on record, and both were provoked by this project.** The first came from about a thousand requests for guessed filenames. The second came from two fetches running at the same time. Both happened on the laptop, before 12 September, and before git history starts.
   - Neither is dated.
   - Neither has a saved answer or a log.
   - Neither has a recorded length beyond "costs days and an email to a Clerk's office" (`CLAUDE.md:58`, `CONTRIBUTING.md:12-15`).
2. **Every other refusal on record was not a block,** and each was over within hours:
   - **9 and 12 Sep:** two documents that answer 403 by themselves.
   - **11 Sep:** two read timeouts. The server was normal at most 61 minutes later.
   - **29 Oct:** two dropped connections. The server answered normally at most about 8 hours later, as seen from a different address.
3. **On GitHub's machine, from 30 Sep to 29 Oct:**
   - 38 runs asked the export, in 51 passes of about 15 requests each.
   - **Exactly one** pass met a dropped connection: 29 October.
   - 23 of the 51 passes met the export failing on the General Court's side: the page timing out at 300 s, or answering "Error Generating ... Execution Timeout Expired".
   - None of those 23 led to a refusal or a block.
4. **On the wire, the 29 October answer looks the same as the only first-hand description of a block in the repository.** That description is `netcheck.py:11-19`: RemoteDisconnected on every request, including the first step of a night. What set 29 October apart from a block is circumstance, not the answer:
   - nothing preceded it;
   - it was the night's first request after 24 hours of silence;
   - a different address found the server answering later that day.
5. **The database answered whole on every occasion it was asked when the export failed:** 3, 4, 5, 6 (rerun), 9, 11 (dry run) and 12 October, "11 of 11 views arrived whole" each time. **On 29 October it was never asked.** A web-server refusal gates it off in `nightly.py`, even though `probe_db.py:109-110` says "A refusal from the web server does not hold this host, and the reverse".

---

## 2. The incidents

**Kinds used below:**
- **BLOCK**: the firewall refusing the address.
- **DOC**: one document refusing.
- **SLOW**: the server slow or timing out.
- **EXPORT**: the export answered, but the files were empty or the page reported an error. This is not a refusal.
- **?**: unresolved.

### 2a. The web server (gc.nh.gov)

**1. The first firewall block. Undated, on or before 4 Sep. Kind: BLOCK.**
- **Machine:** the laptop, from the project's own address.
- **What was asked:** calendar discovery guessing filenames: "two folder spellings, two ways of writing 'No', two day paddings, two extension cases". The firewall "correctly read [it] as a directory scan and blocked the address" (`probe_calendars.py:13-18`, `fetch_calendar_archive.py:20-23`, `fetch_journals.py:64-70`).
- **Requests made:** "about a thousand requests for files that mostly did not exist" (`probe_calendars.py:15-16`).
- **What came back:** not recorded in so many words. `netcheck.py:11-19` is stamped `2026-09-04.4`, the same day as `probe_calendars.py`'s `2026-09-04.9`. It says: "Every request started failing with RemoteDisconnected -- the server accepts the TCP connection and closes it without sending a byte. It did this to the first step of a nightly run, before that run had asked for anything, and to single probes with nothing else going. Fetching worked nine hours earlier." **That this describes block 1 is an inference** from the shared date, not something stated.
- **Back to normal:** "costs days" (`CLAUDE.md:58`; `CONTRIBUTING.md:14-15`). No figure is recorded.
- **What a person did:** emailed a Clerk's office, per the documentation. `netcheck.py` was written, and discovery was rebuilt to read the index rather than guess (`fetch_calendar_archive.py:20-26`).

**2. The second firewall block. Undated, before 12 Sep. Kind: BLOCK.**
- **Machine:** the laptop.
- **What was asked:** two workers at once.
  - The daily snapshot "took no lock, so it could run beside the bill-text lane as a second worker at the same address -- which is how the second block was earned" (`snapshot_gencourt.py:20-27`).
  - "Any run longer than an hour could be joined by a second worker, which is how this address was blocked the second time" (`refusal.py:312-316`; also `watchers/gc_lane.py:17-24`).
- **Requests made:** not recorded.
- **What came back:** not recorded.
- **Back to normal:** "costs days". No figure.
- **What a person did:** the one-worker lock (`refusal.hold`, from 12 Sep, per `gc_lane.py:24`) and the lane.

**2b. A block at 0.7 s spacing. Undated (file stamped `2026-09-04.35`). Kind: BLOCK, possibly the same event as 1 or 2.**
- **Machine:** the laptop.
- **What was asked:** committee-report probes at 0.7 s spacing.
- **What came back:** "the firewall blocked us at 0.7" (`fetch_committee_reports.py:716-717`). Nothing more is recorded.
- **What a person did:** the default `--delay` was raised to 2 s.
- **Note:** the documents count *two* blocks, so this is probably one of them, but the record does not say which.

**3. Two 403s on two documents. 9 Sep, about 11:55 EDT (15:55 UTC). Kind: DOC, on the project's own later reading.**
- **Machine:** the laptop's calendar drain.
- **What was asked:** Senate 2008 `09B.pdf`, then `09A.pdf`.
- **What came back:** HTTP 403 twice.
- **Requests before:** 3,234 PDFs since 22:27 EDT on 8 Sep, about 15 s apart, per the fetch stamps in `queue.csv`. The last one fetched whole was 2008 `1.pdf` at 11:55:23.
- **Back to normal:** the address answered other requests. "The lane's bill-text runs were answered all day on the 12th". On 13 Sep, from 15:26 to 23:13 EDT, the drain fetched 620 Senate calendars of 1998-2008 with no 403 (`queue.csv`). The two documents still 403. No zero-padded name has ever been served: there are 44, all now withheld (`gc_lane.queue:161-178`; `queue.csv`'s withheld rows).
- **What a person did:** `refusal.py` was written that day (stamp `2026-09-09`). Its docstring cites this event: a "chained run" asked the address again "fifty-four seconds later" (`refusal.py:22-27`).
- **Reading:** this is the event the refusal rule was written for, and **the project's own later reading is that it was not a block** (`gc_lane.queue:167-176`: "a finding about 44 documents, not the address -- but it is a reading of the record and not yet a test").

**4. Two read timeouts. 11 Sep, 11:36 EDT (15:36 UTC). Kind: SLOW, an outage.**
- **Machine:** the laptop's lane.
- **What was asked:** `fetch_archive_docket` per-bill pages for 2015-2016, 15 s apart.
- **What came back:** "two 60-second read timeouts 97 minutes in -- the second run in a row to slow or stop about ninety minutes into business hours".
- **Requests made:** about 280 this run, my estimate. 381 of 1,072 pages were cached by then, and 102 of those came from the run stopped at 09:51.
- **Back to normal: 61 minutes at most.** "netcheck at 12:37 found the address answering as it always has" (`watchers/gc_lane.queue:46-51`).
- **What a person did:** ran `netcheck.py`, then `refusal.py --clear`. The lane was "restarted at 12:47 ... on the person's leave, at 25 s a page" (`HANDOFF.md` at `4bbe30d`, line 294).

**5. A deliberate re-ask. 12 Sep, 21:36 EDT. Kind: DOC.**
- **Machine:** the laptop's lane.
- **What was asked:** 2008 `09B.pdf` again, chosen on purpose as the proving run.
- **What came back:** 403, on the first request.
- **Requests made:** 1.
- **Back to normal:** as for incident 3.
- **What a person did:** the lane stopped. The queue calls the choice "a mistake: a 403 on a document already known to 403 cannot say whether the address or the document is refusing, and it costs a day of every fetch" (`gc_lane.queue:161-166`).

**6. 20 Sep, 02:04 EDT. Kind: EXPORT.** The laptop's snapshot got two files empty. Whole files came "at 02:32 and 03:45 on other nights and at every run after 7 a.m." (`nightly.py:2548-2556`).

**7. 27 Sep, 06:33 UTC. Kind: EXPORT.** GitHub's first scheduled night got all 13 files as 3 bytes. Nothing was built. The cron was moved from 06:17 to 08:17 UTC (`.github/workflows/nightly.yml:16-21`; `nightly.py:2548-2551`).

**8. 28 Sep, 08:42 UTC. Kind: EXPORT.** On GitHub, 8 files were empty. The page said "Error Generating Members File : Execution Timeout Expired" (`snapshot_gencourt.py:217-222`). Nothing was built.

**9. 1 Oct, 08:43 to 11:46 UTC. Kind: EXPORT.**
- **Machine:** GitHub, run 36837173742.
- **What was asked:** the export, 6 passes 30 minutes apart.
- **What came back:** the page answered "Execution Timeout Expired" twice and timed out at 300 s four times. 13 of 14 files were 0 or 3 bytes on every pass.
- **Requests made:** about 90 over 3 hours. This did not provoke a refusal.
- **Back to normal:** not within the night, and nothing was built.
- **What a person did:** approved the database fallback (`e55795f`).

**10. 2 Oct, 08:42 to about 17:05 UTC. Kind: EXPORT, about 8½ hours.**
- **Machine:** GitHub. The scheduled run was 36984689602; the person reran it as 37024987876.
- **What was asked:** 6 passes, then 4 more on the rerun.
- **What came back:** the same as 1 October.
- **Requests made:** about 150.
- **Back to normal:** the rerun's fourth pass came back whole at about 13:05 EDT. That time is estimated from the step durations in `nightly-2026-10-02.log~134017`, lines 589-708.
- **What a person did:** reran the night. They also decided that "retrying the export being empty [is not] worth doing 5 times", so the database is now asked at once (`nightly.py:2566-2580`).

**11. 3, 4, 5, 9 and 12 Oct, and the 6 Oct 07:08 rerun. Kind: EXPORT.**
- **Machine:** GitHub. The dry runs of 9 and 11 October met the same.
- **What was asked:** the export, one pass.
- **What came back:** the page timed out at 300 s or answered "Error Generating ... File : Execution Timeout Expired", and 11 to 13 files were empty.
- **Requests made:** about 15 per night.
- **Back to normal:** whole the next night, except that 3, 4 and 5 October failed three nights running.
- **What a person did:** nothing. The database fallback built every one of these nights, and each was CLEAN.

**12. 29 Oct, 08:27:15 UTC (04:27 EDT). Kind: ? (see §3).**
- **Machine:** GitHub, run 40841071509, started 08:21:13 UTC.
- **What was asked:** the export page, then `Docket.txt`.
- **What came back:** "dropped: RemoteDisconnected: Remote end closed connection without response" on both, about 4 s apart (log lines 1657-1658).
- **Requests made: 2,** and the whole fetch took 6 s. GitHub's previous request to the General Court was about 24 hours earlier, in the 28 October night, which got a whole export.
- **Back to normal:** at most about 8 hours, but only on the manager's account of one `netcheck.py` run from a cloud container (200s on both hostnames). No log I can read records it, and it ran from a different address.
- **What a person did:** nothing yet. `state/refused.json` is still in the bucket, and the night is "NOT CLEAN ... Nothing was published" (`last-night.json`).

**After 29 October.** Nothing else in the bucket's logs shows a refusal, a drop or a block. The other two web-server steps the night runs, next session's bill requests and the calendar and journal lists, exited 0 in all 34 logged runs.

### 2b. The other hosts, for comparison

**YouTube.**
- **30 Sep:** the laptop's caption catch-up got "HTTP Error 429: Too Many Requests" on its second recording (`168c653`).
- **11, 19 and 27 Oct:** GitHub's machine got the bot check ("Sign in to confirm you're not a bot") on **one** request each time (`logs/2026-10-{11,19,27}/…youtube-*.log`).
- **The hold works as built.** The record is `state/livestreams.json` → `refusals.runner`:
  - `count: 7`: seven refusals in a row, each met with a single request;
  - `until_iso: 2026-11-03T06:20:33Z`: the hold is now at its one-week ceiling, less 2 hours;
  - `most: 6`: the next run is a small one.
- A person never had to clear it.

**The SQL host (PublicSQL).**
- Every time the night turned to it, it answered whole: "11 of 11 views arrived whole, 168,3xx rows, in 11 connections" on 3, 4, 5, 6 (rerun), 9, 11 (dry run) and 12 October.
- There is no `state/sql-held.json` in the bucket, although `cloud_kit.json:213` carries it. So the hold has never been written on GitHub's machine. That is an inference from its absence.
- The IT office's answer of 15 September (`design_final.md:376`, from wf16): "No problem hitting PublicSQL during a session as it doesn't touch the website."

---

## 3. What tells a block from an outage, on the evidence

### A. What came before it. This is the clearest difference.

| | What this project had just done |
|---|---|
| Block 1 | about 1,000 guessed URLs, most of them missing |
| Block 2 | two workers at once, through hours-long runs |
| Block 2b | 0.7 s spacing |
| 11 Sep (outage) | a long crawl at 15 s (in between) |
| 2 Oct (outage) | about 150 requests over 9 hours, at 30-minute gaps, with no refusal |
| 29 Oct (outage?) | **nothing**: the first two requests of the night, 24 hours after the last |

Every recorded block followed abnormal behaviour by us. No recorded block followed a quiet period.

### B. What came back, on the wire. Weak, and it cuts against the design.

- **The code reads these as refused** (`refusal.py:265-307`): 403, 429, 503, `Retry-After`, or the body markers `Web Page Blocked|Attack ID`. Drops are "this address's usual sign of refusing" (`refusal.py:275-276`).
- **The only first-hand description of a block** is drops on everything (`netcheck.py:13-19`). 29 October's answer, RemoteDisconnected on the first request, **cannot be told from that on the wire.**
- **The block page has never been captured.**
  - `BLOCKED = re.compile(r"Web Page Blocked|Attack ID")` was already in the first commit (`4bbe30d`, in `fetch_bill_text.NOT_A_BILL` and `fetch_legislation.py:226`).
  - Every "Attack ID" string in the repository is a preflight fixture (`preflight.py:56716`, `77518`, `77796`, …).
  - No log in the bucket mentions meeting one.
  - "Web Page Blocked … Attack ID" is how a Fortinet-style firewall page reads. That is **a guess** from the wording, and nothing in the repository says so.
- **The only dated 403s** (9 and 12 Sep) were per-document, not the address.
- **A 503 has never been recorded from the General Court,** in any log or comment. `classify()` treats an HTTP 503 as refused (`refusal.py:272,286`). The code is inconsistent about a 200 whose body says "Service Unavailable": `fetch_legislation.py:226-227` reads it as `BROKEN` ("a struggling server"), and `fetch_bill_text.py:346` as "the server refusing". The evidence does not decide the 503 question.

### C. How long it lasted.

- **Blocks:** "days", with no figure anywhere.
- **Outages:**
  - 11 Sep: at most 61 minutes;
  - 2 Oct: about 8½ hours;
  - 29 Oct: at most about 8 hours, from another address;
  - 3, 4, 5, 9 and 12 Oct: fixed by the next night.

### D. Where "it's back" was seen from.

- `netcheck.py:23-27` and `38-42` themselves say that the browser test **on the same machine** is what tells "this address is blocked" from "the server is down".
- That test is impossible on GitHub's runner, which is gone when the run ends.
- 29 October's check came from a different address, so it shows the server was up. It cannot show that GitHub's address was not blocked.
- The sibling report (`read_refusal.md` §2) found that `netcheck.py:162` counts any HTTP status, a 403 included, as "got through". The "200s" of 29 October should be confirmed from that run's printed table if anyone kept it.

### E. The server's own distress is common, and it has not provoked the firewall.

- In 51 passes from 30 Sep to 29 Oct, the export's page failed 23 times:
  - it timed out at 300 s 15 times;
  - it answered "Error Generating … Execution Timeout Expired" 8 times.
- `snapshot_gencourt.py:257-262` reads a page timeout as "slow", not a drop, and none of the 15 led to any refusal.
- 29 October's drop may be the same server in trouble. That is **a guess**: nothing shows it.

### F. The night's own rule treated 29 October more harshly than a long crawl.

- The page's drop counts toward the two (`snapshot_gencourt.py:587-588`). The second drop records a refusal at once (`:620-623`).
- The "once more in a minute" retry (`:624-629`) is only for a file's *first* drop, after the page has already counted. So the two drops were about 4 s apart: `--delay` defaults to 4.0 s, ±25% (`:500`, `:592`).
- The "two drops end a run" rule was written for crawls of hundreds of pages (`fetch_archive_docket.py:30-43`). Here it was applied to the first two requests of a night.

---

## 4. Where the evidence is thin

- **The two real blocks have no first-hand record.** There is no log, no saved response and no date. Their wire shape is inferred (block 1 from `netcheck.py`) or unknown (block 2). The laptop's `logs/gc_*.log` and `logs/gc_lane.log` are not in the bucket backup and not in this clone.
- **No length is recorded for either block,** beyond "days" and an email.
- **29 October is a sample of one** drop in about 750 export requests from GitHub. Its "back to normal" rests on a single unlogged check from another address.
- **No log records GitHub's outbound address.** No log prints it, so whether 29 October's refused address is the one the next night will use is unknown. GitHub-hosted runners usually change address between runs; that is general knowledge, not shown here.
- **The records disagree on the founding event:**
  - "fifty-four seconds" (`refusal.py:22-24`; `HANDOFF.md` at `4bbe30d`, lines 121-123) against "twelve seconds" (`CLAUDE.md:76-77`);
  - "eight hours into an unbroken one" (`watchers/rest.py:6-7`) against the queue's 13½ hours, from 22:27 to 11:55;
  - whether the "664 calendars … each with HTTP Error 403" (`fetch_senate_calendars.py:179-181`) were 664 answers or one 403 written against the rest is not recorded. The queue shows those 664 are now 620 fetched whole on 13 Sep plus 44 withheld.
- **The 9 Sep "not a block" reading** is the project's own reading of the record, and it says it is not yet a test.

---

## 5. Precedents for resuming without a person

**1. YouTube captions** (`src/ops/livestreams.py:291-311`, the docstring "A REFUSAL").
- **The rule:**
  - nothing is asked for 12 hours;
  - the next run opens with one request and goes on only if it is answered;
  - each refusal in a row doubles the hold: a day, two, four, then a week, each 2 hours short;
  - the next runs are small: 6 new recordings, then 2 more per clean run.
- **Constants:** `HOLD_HOURS = 12`, `HOLD_MAX = 168`, `EARLY_HOURS = 2`, `AFTER_REFUSAL = 6`, `EASE = 2` (`:510-521`). The hold is `Refusals.note` (`:1249-1292`).
- **The check:** `preflight.py:16960` `_ls_hold`, "after a refusal nothing is asked for twelve hours, the wait doubles, and the next runs are small". It pins the constants and drives a 429 through two nights.
- **Its history:**
  - It arrived with the feature the person asked for on 25 September (`55b458d`: "The person asked on 25 September that the nightly add the timestamps …"). The first hold was 36 hours.
  - It was shortened to 12 hours, doubling, on 1 October, after the laptop's 429 of 30 September (`168c653`).
  - "Six was the size the pacing was agreed at" (`livestreams.py:131-132`, `:518-520`).
- **Thin:** no commit or comment records the owner approving the *resume-by-itself* rule in so many words. What is recorded is the request for the feature and the agreed pacing.

**2. The SQL host's hold** (`src/fetch/gc_db/probe_db.py:73-110`).
- It expires on its own and lengthens: `HOLD_HOURS = (20, 44, 92, 164)` (`:115`). One connection is tried a night, and one that opens ends it.
- It says why, against the web server's rule (`:86-89`): "That is the deliberate difference from the web server's rule, where only a person clears a refusal: a month unattended needs it, and one connection a night is not what that rule exists to prevent."
- It shipped in `e55795f` (1 Oct) as part of the fallback "the person approved … gently". It has never fired on GitHub's machine.

**3. The export's own retry.**
- An empty export was re-asked automatically, every 30 minutes up to 6 times, from 28 September (`dc401e6`).
- On 2 October the person replaced that with "the database at once" (`nightly.py:2565-2612`).
- So the night already resumes by itself after an *export* failure, by changing source, not by asking again.

**4. The live layer's holds,** designed, not built (`design_final.md:436-444`): "None needs a person to clear it; each ends by the next New Hampshire day, as `probe_db` learned."

**5. The clock gate** (`origin/feat/night-clock`, `nightly.py` docstring).
- The person approved the side steps asking only between 08:00 and 12:00 UTC ("The existing bill request and list page steps can stay within 4-8am", 26 Oct). A step that cannot finish in time is "not asked for", and the night still publishes.
- It does not touch how a refusal is read.

---

## 6. The owner's idea against this evidence

**Where it plainly helps: the database as the night's source while the web server is out.**
- PublicSQL answered whole on all 7 occasions it was asked in October, 3 to 12 October.
- On 29 October it was not asked, because of three gates:
  - `nightly.py:1587-1589` breaks out of the fetch loop on a refusal before `from_database`;
  - `:1626` gates the study views, the term data, the bill requests, the statutes and the lists on `not refusal.MARK.exists()`;
  - the docstring at `:317` makes "no refusal from the web server is on file" a precondition of the fallback.
- Against those gates:
  - `probe_db.py:109-110`: "A refusal from the web server does not hold this host, and the reverse";
  - the IT office: PublicSQL "doesn't touch the website".
- **On this evidence the 29 October night could have been built from the database,** as 3 to 12 October were. The site would then have been a day fresh, not a day stale, while the web server's question waited.

**Where it does not help as written: the live Worker as the signal that the web server is back.**
- The Worker never asks gc.nh.gov (`design_final.md:43`, `:60`).
- It reads PublicSQL only in three states (`design_final.md` §2.3, `:341-347`):
  - **Hot or Warm:** around a sitting;
  - **Heartbeat:** weekdays 09:30 EDT to 18:00, 1 January to 30 June, and in the 14 days after a sitting;
  - **Off** otherwise.
- On 29 October, with no sitting and outside January to June, it would have read **nothing**.
- When it does read, it reads from Cloudflare's addresses: a third address, which says nothing about GitHub's.
- It *can* show that the SQL host is healthy in session season. That is the half of the night it could vouch for.

**What would show the web server is back for GitHub's address.** Only a request from GitHub's runner shows that.
- The recorded recoveries were 1 hour or less, about 8½ hours, about 8 hours and one night.
- That fits a single, spaced knock later the same morning or the next night.
- But it rests on three events, and none of them was a firewall block.
