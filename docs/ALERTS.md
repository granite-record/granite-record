# Alerts: what each one means, and what to do

Every alert reaches you as an email from **Healthchecks**. Each Healthchecks check emails when it goes
**down** and again when it comes back **up**, not every night in between. So a problem that lasts three
nights is one email, and the "up" email is the sign it has cleared (nightly.py:5763-5766,
ARCHITECTURE.md:274-276). A check goes down in one of two ways:

- **With a body:** the system sent `/fail` with a sentence saying why. The sentences are quoted below.
- **Silent, with no body:** the pings stopped. Something did not run at all.

The check names are the ones on the Healthchecks dashboard. The code knows each check by its secret,
which is named after each heading. Nothing here is sent by a test run: only `main` pings (nightly.yml:261-266).

**Where commands run.** "On the laptop" means PowerShell (or cmd) on the laptop, opened in the
repository's folder. Every command below is the same in either. Before running anything that asks the
General Court, look at `archive/.lock`: a fresh one means a fetch is already running, and two at once is how
the second block happened (CLAUDE.md, "Before assuming nothing is running").

| Check | Pinged by | When it is down, it usually needs you? |
|---|---|---|
| Granite Record nightly | the nightly, every night | Sometimes: read the body |
| night warnings | the nightly, every night | Rarely: things to look at, not emergencies |
| graniterecord.org published | the publish job | Yes, if it says a night is waiting for approval |
| follow sender | the email sender, every hour | Rarely |
| graniterecord-live | the live Worker, every 2 minutes (coming with the live layer) | Rarely |
| a refusal is yours | the nightly and the knock (coming with outage recovery) | **Always** |

---

## Granite Record nightly (`HEALTHCHECKS_URL`)

Each night it is sent `/start` when the night begins, and when the night ends either a plain ping or `/fail`
with the alert as the body (nightly.yml:267-286, 568-596). The body is one or more of the sentences below
(`alerts_of`, nightly.py:5826-5852).

| Email says | Means | Needs you? | What to do | Fixes itself? |
|---|---|---|---|---|
| *(down, no body)* | No night reached its end: it did not start, or it started very late. | Look once. | Open GitHub → Actions → nightly. The night-timer Worker starts it at 08:17 UTC, and GitHub's own schedule is the fallback (workers/night-timer/index.js:1-30, 78-79). | Yes, when a night finishes. |
| "A refusal from the General Court has been on file since {time}. Every fetch waits until a person clears it: python3 netcheck.py says what kind it was, then python3 src/ops/cloud.py clear-refusal." (nightly.py:5837-5839) | The General Court's server refused a request. Nothing asks them again until you say so. | **Yes.** | On the laptop: `python3 netcheck.py`, and read its table, not its last line (docs/proposals/OWNER_STEPS.md:20@feat/outage-recovery). Then `python3 src/ops/cloud.py clear-refusal`, and `python3 refusal.py --clear` if the laptop holds a copy. netcheck itself asks the General Court, so run it once and never beside another fetch. | No. |
| "The General Court's database is on hold: …" (nightly.py:5846) | The database could not be reached. The sentence says until when nothing asks it (src/fetch/gc_db/probe_db.py:162-171). | No, unless it says the login was refused. | If it says "until the credentials in probe_db.py are changed", the published password has changed: ask for the code to be updated. | Yes, at the time it names. |
| "Checks of tonight's built site failed -- held for approval: {names}." or "The checks of tonight's build did not run, so the night waits for approval." (nightly.py:4872-4882) | Tonight's site was built, but a check of it failed, so it was not published on its own. | **Yes.** | Have the named checks read, then approve or leave the night (see *graniterecord.org published*). | No. |
| "The night was not clean: …" (nightly.py:5850-5851) | Something in the night went wrong. The rest of the sentence says what, e.g. "The build failed." (`plain_why`, nightly.py:2357-2399). | Read it. | Nothing unless it repeats on a second night. A refusal named here is the row above. | Yes, the next clean night. |
| The weekly job failed (weekly.yml:214-237) | Sunday's committee-roster run failed. It publishes nothing. | No. | Nothing. | Yes, the next good night pings up. |

## night warnings (`HEALTHCHECKS_WARN_URL`)

While any warning stands, this check gets `/fail` with the warnings as the body. When none stands, it gets a
plain ping (nightly.yml:597-617; `warns_of`, nightly.py:5815-5823). These are things to look at, not
emergencies: the site is still published.

| Email says | Means | Needs you? | What to do | Fixes itself? |
|---|---|---|---|---|
| "The night waits for approval, so the live site is not updated until a person approves it: {why}. Approve the newest night waiting in production-review; an older one's site is kept only three days." (nightly.py:5810-5812) | A built night is held for you (ARCHITECTURE.md:168-171). | **Yes, within three days.** | On GitHub, approve the newest night waiting in the `production-review` environment. | No. |
| "Checks of tonight's built site against the record failed -- published all the same: {names}." (nightly.py:4891-4892) | It was published, but something disagrees with the record. | No hurry. | Have the named checks read. | Yes, when they pass. |
| **The captions inbox.** "Nothing has arrived in the captions inbox since {date} ({n} days), and {n} recordings finished more than 3 days ago wait for their start times … The laptop's evening run (livestreams.py --to-inbox, from Task Scheduler at 7:30 pm) sends them, and they arrive again once that run is on, logged in and answered by YouTube." (nightly.py:3856-3864) | The laptop has not sent caption results for 3 days or more, so recent recordings show approximate start times. | **Yes, today's case.** | Have the laptop on and logged in at 7:30 pm, so Task Scheduler's evening run happens. `logs/captions-inbox.log` on the laptop says what it last did. | Yes, once results arrive. |
| **The laptop's caption run, 48 hours.** "The laptop's last caption run on record is of {time} UTC, {n} hours ago: its evening run (livestreams.py --to-inbox, from Task Scheduler at 7:30 pm) has not reported for two evenings or more. It runs again when the laptop is on and logged in at 7:30 pm; logs/captions-inbox.log there says what it last did." (nightly.py:3881-3886; 48 hours is `LAPTOP_RUN_STALE_HOURS`, :3544) | Same cause as the row above, seen from the laptop's side. If no record came down at all, it says "No record of the laptop's caption runs came down tonight …" (:3872-3877). | **Yes, today's case.** | As above. | Yes, after the next evening run. |
| "The General Court's record has not moved for {n} days: …" (nightly.py:3647-3659) | Their Docket has no new lines for longer than any season since 2015. | Usually not. | If the sentence says their export stopped refreshing, that is "the General Court's IT office's to start again". | Yes, when it moves. |
| Database pieces not taken for 2 nights or more (nightly.py:3713-3720) | A hold or a dropped connection, or a change in their data. | Only if it lasts. | Have the night's log read. | Usually. |
| The laptop's share behind (nightly.py:3770-3779) | "It moves again when the laptop's fetches run and seed-kit sends what they made, both a person's to start." | **Yes.** | Start the laptop's fetches, then `python3 src/ops/cloud.py seed-kit` on the laptop. | No. |

Not emailed: the run-page warning "{n} recordings finished over 3 days ago keep the schedule's approximate
start" (nightly.py:5433-5438) stays on the run's page (ARCHITECTURE.md:293-294).

## graniterecord.org published (`HEALTHCHECKS_PUBLISH_URL`)

Pinged only when production has been deployed (nightly.yml:742-757).

| Email says | Means | Needs you? | What to do | Fixes itself? |
|---|---|---|---|---|
| *(down, no body)* | The live site has not changed for longer than the check allows. Usually a held night nobody approved (ARCHITECTURE.md:285-288). | **Yes.** | Approve the newest night waiting in `production-review`. | Yes, at the next deploy. |
| "The publish job failed, so the live site was not updated: {run address}" (nightly.yml:768-792) | Deploying failed. | Look once. | Open the run address. | "the next published night brings it back up" (nightly.yml:765-766). |

## follow sender (`HEALTHCHECK_URL` on the follow Worker)

It runs every hour on the hour (workers/follow/wrangler.toml:40-46). It sends email to readers from 8:00 to
20:00 New Hampshire time (workers/follow/sender.js:60-61). Every run pings: a plain ping when the run did its
work, or `/fail` with `problem: {code}: {text}` lines (sender.js:573-582). It never emails you itself.

| Code | Text (sender.js:107-115) | Needs you? | Fixes itself? |
|---|---|---|---|
| *(down, no body)* | The Worker stopped running: "Healthchecks writes when the pings stop" (sender.js:42-43). | Look once. | No. |
| `tonight` | "tonight's changes file was still missing at noon" | **No: today's late-night case.** Before noon the sender waits each hour; at noon it sends what earlier nights had, and the late night's news goes out the next morning (sender.js:31-32, 396-408). | Yes. Once nobody else is due that day, the next run pings up (sender.js:358-364). If the night itself failed, *Granite Record nightly* says so. |
| `site-follow` | "the site's follow pages do not answer, so nothing was sent" | Look if it repeats. | Usually. |
| `current` | "the site's current.json is missing or unreadable" | Look if it repeats. | Usually, after the next publish. |
| `config` | "the sender's configuration is missing" | **Yes:** a setting of the Worker is missing. | No. |
| `resend-auth` | "Resend refused the key or the sending domain" | **Yes:** the Resend key or domain. | No. |
| `resend-rate` | "Resend's rate limit stopped the run" | No. | Yes, next hour. |
| `resend-down` | "Resend failed three times in a row, so the run stopped" | No. | Yes, when Resend answers. |
| `all-refused` | "every email this run tried was refused" | Look if it repeats. | Sometimes. |
| `run-failed` | "the run stopped on an error of its own" | Look if it repeats. | Sometimes. |

## graniterecord-live (`HEALTHCHECK_URL` on the live Worker)

**Coming with the live layer** (`live/session`, about 3 November). The check is set up with period 2
minutes and grace 10 minutes (workers/live/README.md:116-117@live/session). It is pinged every 2 minutes all
day, plain or `/fail`, and the ping's body says why (index.js:62, 94-105, 385-389@live/session).

- **One run's failure:** clears on the next run. Examples: YouTube's quota spent, "waits for midnight
  Pacific" (youtube.js:387-389); "{n} file(s) were due and not written" (index.js:373-377); "the run stopped:
  …" (index.js:381-383). Nothing to do.
- **Standing failures**, sent on every run until mended (index.js:107-127):
  - "control.json cannot be read …: put one of control/*.json". **Yes:** put a control file back (README.md:168-170).
  - "there is no YOUTUBE_API_KEY secret …". **Yes:** on the laptop, `npx wrangler secret put YOUTUBE_API_KEY …` (README.md:102-111).
  - "YouTube refused the key …". **Yes**, for a new key: put `all-off.json`, wait one run (2 minutes), then put `sql-off.json` (README.md:163-166).
  - "{n} looks at YouTube in a row have failed". No: it clears on a good look (youtube.js:352).
  - "votes held for the day: …" or "votes held for 30 minutes: …" (votes.js:202-213). No: "each ending by the next New Hampshire day at the latest, none needing a person" (votes.js:40-41). The exception: "the published password may have changed; read the PDF again".

## a refusal is yours (`HEALTHCHECKS_PERSON_URL`)

**Coming with outage recovery** (`feat/outage-recovery`). Set up as Simple, period 1 day, grace 1 day
(docs/proposals/OWNER_STEPS.md:27-31@feat/outage-recovery). "Down means a person must act; the email's body
says why." (:28-30)

| Email says | Means | Needs you? | What to do |
|---|---|---|---|
| "A REFUSAL IS YOURS: the General Court refusal met by {where} at {when} is a person's to clear: {why}. …" (refusal.py:1469-1474@feat/outage-recovery) | A refusal that GitHub could not settle by itself. | **Always.** | On the laptop: `python3 netcheck.py` (read its table, not its last line), then `python3 src/ops/cloud.py clear-refusal`, then `python3 refusal.py --clear` (OWNER_STEPS.md:20-22). If the email adds "The address was told no", the General Court's IT office or the Clerk's office "may need a message before anything asks again" (refusal.py:1475-1476). |
| *(down, no body)* | "An email from silence means the night stopped reporting, not that a refusal is yours" (OWNER_STEPS.md:39-41). | Look at *Granite Record nightly*. | |

A refusal that GitHub is still testing itself does not use this check. It appears in the nightly's own email,
which says "Nothing is needed from you on GitHub's side" (nightly.py:6644-6657@feat/outage-recovery).

## What does not email you

- **"Report a problem"** stores each report and sends you nothing (functions/api/report.js:311-317). If the
  report cannot be stored, the box offers the reader an email to contact@graniterecord.org instead
  (src/pages/app.js:6783).
- **The night-timer Worker** alerts no one. If it cannot start the night, GitHub's schedule does it later,
  and *Granite Record nightly* notices a missing night (workers/night-timer/index.js:78-79).
- **GitHub** sends its own emails about failed runs and about nights waiting in `production-review`
  (ARCHITECTURE.md:272). Those say the same things as the run's page.
