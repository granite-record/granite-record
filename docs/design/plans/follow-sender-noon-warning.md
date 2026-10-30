# The follow sender's noon alert on a late night: plan

The owner's direction, relayed 30 October 2026: the follow sender's noon /fail
on a late night becomes a warning when the nightly's own check already reports
it.

## Today

`workers/follow/sender.js` runs hourly. From 8:00 New Hampshire time it waits
for tonight's changes file (`/changes/<today>.json`). If the file is still
missing at noon (`WAIT_UNTIL_HOUR = 12`), it sends what it has and records the
problem `tonight`. Every problem makes the run's Healthchecks ping a `/fail`,
so the sender's check emails the owner.

A night that did not publish by noon (late, failed, or held for approval) has
already been reported by the nightly's own checks: the night's check, or the
"waiting for approval" warning check. So the owner gets two emails for one
cause, and the second one says less.

## The rule

At noon, with tonight's file missing, the sender reads `current.json`'s `date`,
which it already fetches. That is the night the site last published.

- **`date` is before today: the night has not published.** The nightly's
  checks report it, so `tonight` is a **warning**, not a problem. The run's
  ping is a plain ping, and its body carries
  `warning: tonight: tonight's changes file was still missing at noon; the site
  last published <date>, which the nightly's own check reports`. The log notes
  `sender.tonight-missing-night-late`. No email from the sender.
- **`date` is today: the night published, but tonight's file is missing.** Only
  the sender can see this (a publish that lost the file, or a changes step that
  wrote none), so it stays a problem and a `/fail`, as today.
- **`current.json` is missing or unreadable.** This is already its own problem
  (`current`) and stays a `/fail`.

This needs no new secret and no request to Healthchecks' API. The sender judges
from what the site itself published.

## Code

- `sender.js`: a `WARNINGS` map beside `PROBLEMS` (`tonight-late`), and
  `out.warnings`. Where `tonight` is pushed, push `tonight-late` instead when
  `current.date < when.date`. `ping()` writes `warning:` lines into the body
  and sends `/fail` only for `out.problems`.
- `README.md` (follow): the "who is told" table gains the warning row.
- `CHANGES_FORMAT.md`: no change. `date` already means "the newest night".

## Tests

- `tests/follow/` (the sender's own node tests, run by preflight): a noon run
  with tonight missing and `current.date` = yesterday gives a plain ping with
  the warning line and no `/fail`. The same with `current.date` = today gives
  `/fail`. Before noon, neither: still waiting, as today.
- A revert proof: dropping the date test makes the first case `/fail` again,
  and the test fails.

## Caveat

The rule assumes the nightly's check has emailed by noon ET for a night that
has not published. Its period and grace are set in the Healthchecks UI, not in
the repository, so I could not read them. **To confirm with the owner:** the
nightly check's grace ends before 12:00 ET. If it ends later, the owner still
hears from that check, only later than noon, and the warning is still correct.

## Size and deploy

Two files plus tests: one reviewer. It changes the Worker, so the owner
redeploys the follow sender (`wrangler deploy` in `workers/follow/`), the same
step already planned for Monday morning. If it is ready in time, it can ride
that redeploy. Otherwise it waits for the next one.
