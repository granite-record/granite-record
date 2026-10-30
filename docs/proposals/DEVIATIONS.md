# Where the build departs from the approved design

The design is `design_final.md` with `design_addendum_hourly.md` taking
precedence (the owner's "defaults" to D1-D6 on 29 October 2026, knocking
hourly). Where it was wrong against the code, or silent, the build took the
simpler safe answer, and says so here, one entry per point, in the commit
that made it.

## Commit 1: the record says what it was

1. **`whose()` with no record on file returns `("none", why)`.** The design
   gives only `"night"` or `"person"`. A missing record is neither: a gate
   that asks `whose()[0] == "night"` stays shut, and a sentence that says "a
   refusal is yours" (`person_line`, later) is not written about nothing.
2. **A 503 whose `Retry-After` reads as neither seconds nor an HTTP date is
   not "unavailable".** The design says only "seconds or an HTTP date".
   `unavailable()` returns `None` for it, so the record's kind is
   `"refused"`: a person's, the worst reading of an answer that cannot be
   read. A date already passed is 0.
3. **`machine`, `ref`, `dry` and `run_id` are written on every record**,
   with a kind or without, as §2.1's "with these fields added" reads.
   `retry_after` is written only for `"unavailable"` and only when the
   server named a wait (non-zero).
4. **The committee pages fetch's kinds are held by the existing
   `_committees_fetch_stops`**, which the design does not name: it now
   asserts each record's kind (a 403 and the block page `"refused"`, two
   drops `"dropped"`, a bare 503 `"unavailable"` with its wait).

## Commit 2: the ladder and the knock's state

5. **`KNOCK_ANCHOR` is the function `knock_anchor()`**, read from
   `NIGHT_WINDOWS` at each call. A constant computed at import would not
   follow a window moved by a check's monkeypatch (H3, commit 4).
6. **`knocks.json` lives beside the record: `knocks_file()` is
   `MARK.parent / "knocks.json"`.** `KNOCKS` is `archive/knocks.json` as
   the design names it, and that is what `knocks_file()` gives in the
   working folder. A check that points `MARK` at a temp folder then keeps its
   knocks there too, never in `archive/`: preflight runs on GitHub's
   machine, where `note()` starts a chain.
7. **`note()` starts `current` for a record whose own fields make it the
   night's (whose() conditions 1 to 5), on GitHub only, whatever the switch
   and the settings say at that moment.** The design says "for a record that
   is the night's to test". The switch is read where it gates (`whose()`,
   condition 7), so a record noted while the method is off, and switched on
   within 16 days, resumes the same chain (design_final §2.11), and a
   relapse noted while it is off still carries its count.
8. **The knock's writers read the test clock.** `knocking()`, `knocked()`
   and `drops_allowed()` take the time from `GRANITE_CLOCK_UTC` when it is
   set, as every gate already does, so a check can drive a chain through
   them. `note()` still stamps a record with the real clock, as before: a
   check that sets the clock and notes a refusal reads its age as it always
   did.
9. **`knocked("whole")` lifts only the record the chain names.** If the
   record on file no longer has the sha `current` names, nothing is lifted
   (it returns `"kept"`). Under the lock this cannot happen; the design is
   silent on it.
10. **A `knocks.json` that does not read is never written over.**
    `whose()` reads it as a person's, `drops_allowed()` as 1, `knocking()`
    raises before any request, and `note()` prints that the chain was not
    started. What it held of past lifts is not lost to a rewrite.
11. **Condition 5 of `knock_due()` (a claim in flight) is implied by
    conditions 3 and 4** for every rung the settings allow: a claim counts
    as the last request (§1.3), and half the smallest rung, 30 minutes,
    exceeds `KNOCK_JOB_MINUTES`. It is kept, as designed; H5's in-flight
    case fails only when both rules are removed, and the proofs say so.
    Likewise `note()`'s `GITHUB_ACTIONS` test and the record's `machine`
    field are the same fact: C2b's laptop case fails with both removed.
12. **A claim's reuse by `knocking()` is left to commit 4**, with the claim
    itself (`--knock-claim`): commit 2 builds what reads a claimed entry
    (the ladder, the lost-claim rule, a run's own claim not counted).
13. **`force()` takes the lift** (`force(d, lift=entry)`), and
    `refusal.py`'s status is a new `say_whose()`. The status line that said
    an old record "no longer stops anything" now says the lane and GitHub's
    night still stop at it (the drift design_final §16 names).

## Commit 3: the bucket knows a lift

14. **"A lifted record in the bucket is absent to GitHub" is built in
    `state-down`, on main's own run only.** The addendum (§7, item 3) says
    `gc_quiet()` and `whose()` treat it as absent "for every GitHub reader".
    Every fetcher reads `archive/refused.json` itself (the snapshot asks
    `MARK.exists()` before each request), so the one place that makes it
    absent to all of them is the copy never coming down: on GitHub's
    machine, main exactly, not a dry run -- `lift_refusal()`'s own
    conditions -- `state-down` leaves a record whose sha the bucket's
    `knocks.json` lists as lifted in the bucket, records it as taken, and
    that run's `state-up` moves it. A dry run still brings it down and stops
    at it: the narrower reading, and the safe one.
15. **`clear-refusal`, `refusal_unsent()` (the send-night check) and
    `unsent_after()` (state-up's marker) read the lifts too.** The design
    names `pull_refusal` and `send_refusal`; these three gave the same
    "send it" advice for a lifted copy, and now do not.
16. **A lifted record still in the bucket, met by a pull, is brought down
    as before** (when the laptop holds none) and said to be lifted: the
    laptop then stops at it until a person clears it, the stricter way.
17. **C9 is a new check, `_cloud_pull_lifted`**, beside `_cloud_pull`
    rather than inside it. It drives `pull_refusal` and `send_refusal`
    directly on folder buckets, and a bucket that lands the lift right after
    its first read proves both orders. `_cloud_pull` keeps
    its own cases; its reader of what pull can reach still finds no write.

## After the review of 62e7406: the one reader takes bytes

18. **`whose()`, `chain()`, `knock_due()` and `knock_schedule()` refuse a
    dict (`TypeError`).** design_final §2.2 gives `whose(d=None, ...)` with
    `d` "refused.json", silent on its form, and commit 1 took a dict as well.
    But `knocks.json` names its record by the sha of refused.json's exact
    bytes, and a dict has none: read as one, a record's `person`, its
    relapses, a lost claim and the chain's start were all passed over, and
    `whose(dict)` said "night" where `whose(bytes)` said "person". A caller
    holding only the fields asks `_its_own()`, which is conditions 1 to 5.
19. **`knock_due()` is `(False, None)` for every record `whose()` does not
    call the night's**, not only once the cap comes first (addendum §1.3).
    A knock that made the record a person's, a fourth relapse, a lost claim,
    the switch off, a setting typed wrong or the record's own fields: no
    knock is ever due for a person's record, whoever asks, and the gate
    (`whose()` and `knock_due()`) cannot be opened by asking only one half.
20. **A relapse within `RELAPSE_HOURS` of a lift carries that chain even
    when a person cleared a record in between** (`_start_chain`).
    design_final §2.2 says "a person's clear never writes `lifted`, so
    nothing is carried", reading a clear as starting afresh. GitHub's night
    cannot see a person's clear: `clear-refusal` records it only on the
    machine that ran it, and `knocks.json` is written by `refusal.py` alone.
    The carry is the stricter reading, and is kept: the carried `since`
    reaches `KNOCK_DAYS` sooner and the carried relapses reach
    `RELAPSES_MOST` sooner, so the record becomes a person's sooner, and the
    next knock is timed from the new record's own drop, which is later than
    every carried knock.

## After the review of 62e7406: the lift's order, and the switch

21. **`lift_refusal()` sends `state/knocks.json` with the lift in it, reads
    it back, and only then keeps and deletes `state/refused.json`.**
    design_final §2.6 lists the move and the "cleared" record but no order,
    and commit 3 moved the record first, so a laptop's pull in between met a
    bucket holding neither the record nor the lift: a FAIL for a copy under
    24 hours, and the advice to send it back for an older one, which
    `send_refusal` would then do. Addendum §7 rule 1's argument (pull reads
    the record, then the lifts) holds only in this order. A put that fails
    or does not read back moves nothing and is a failure in state-up's list;
    the bucket's `knocks.json` is put over only where it is still the copy
    this machine took down, as state-up's own loop would.
22. **The switch gates the lift in the bucket and state-down's lifted skip**
    (`knock_switched_on()`, i.e. `refusal.knock_on()`, on GitHub's machine).
    With `NIGHT_KNOCK` not exactly `on`, the third check unset or a setting
    typed wrong, every `state/refused.json` comes down and stops main's
    night, a lifted one included, and none is moved: the night as it was
    before this branch. Two things stay as they are with the switch off, and
    are said here: `drops_allowed()` is still 1 for a week after a lift
    (stricter: at most one request fewer on a night); and `send-refusal`
    still never sends a lifted record (design_final §2.6), because the
    laptop cannot read the switch. So a lifted record has no command that
    puts it back; a person who wants the night stopped turns the method off,
    and any refusal met afterwards stops it as before.

## After the review of 62e7406: nothing of the laptop's waits behind a record a machine may lift

23. **A laptop's own refusal takes the place of a record GitHub's night may
    lift, and any refusal takes the place of one the knock has lifted**
    (`cloud.waits_behind`, `send_refusal`). design_final §2.6 says only that
    `send_refusal` never sends a sha in the bucket's `lifted`; the old rule
    that a send never writes over the bucket's record assumed only a person
    could lift that record, and a person's `clear-refusal` names the one
    waiting. A knock's lift names nothing, so a 403 met on the laptop behind
    GitHub's drop record was orphaned when the knock lifted it, and GitHub's
    night then asked the General Court. Now the laptop's record is put in
    the bucket's place, the old one kept under `replaced/<day>/` as
    `clear-refusal` keeps it, and main's night stops at a person's record,
    which nothing lifts. Behind a record only a person can lift (no kind, a
    403, the laptop's, a dry run's) it still waits, marked, as before.
    `pull`, state-up's `unsent_after` and the send-night check report the
    waiting case as a failure naming `send-refusal`, and `pull` no longer
    sets this laptop's own record aside because the bucket's GitHub record
    is newer. One case still waits: a copy of a GitHub record here (the
    night's to test too) behind another GitHub record not lifted -- both are
    the night's own kind, and the bucket's is the one its chain names.
24. **`send-refusal` reads `state/knocks.json` only where a record here or
    in the bucket is one the night may lift (`cloud.liftable`, i.e.
    `refusal._its_own`), and sends all the same when that read fails.**
    Addendum §7 rule 2's order (the record, then the lifts, then the put)
    stands for those records. A refusal met on the laptop is never lifted,
    so its send no longer depends on the read at all; and a lifted record
    sent back because the read failed stops nothing while the night's
    testing is on (main's state-down leaves it in the bucket and its
    state-up moves it) and stops the night when it is off, the safe way.

## After the review of 62e7406: the night follows no redirect

25. **The snapshot and the committee pages fetch follow no redirect, and
    read a 3xx as "refused"** (`refusal.no_redirect_opener()`, kept as each
    module's `_OPENER`; `refusal.redirected()`). design_final names a
    no-redirect opener for the knock only (§2.4), while for_owner tells the
    owner that a redirect stops everything at once; on the night urlopen
    followed a 302 to its Location and read the answer as a failed file, so
    the snapshot asked every other file and recorded nothing. `classify()`
    is unchanged, as design_final §5 has it, and as `fetch_legislation`'s own
    check pins (its 3xx is an ordinary failure, through an opener of its
    own); the two night fetchers ask `redirected()` first. The opener holds
    no `HTTPRedirectHandler` of any kind, so the knock (build plan commit 4)
    can take the same one and meet H6 as written. **Not changed here**
    (closed since, by 115 below): the night's other two General Court fetches,
    `src/fetch/gc_web/fetch_lsrs.py` (`get()`, its two `urlopen` calls) and
    `src/fetch/gc_web/fetch_calendar_archive.py --listing` (`_get()`), still
    follow a redirect. They ask only on a night with no
    refusal on file, after the export answered whole; the reviewers' finding
    named the snapshot and the committee pages, and these two are left for
    the next stage rather than changed unreviewed.

## After the review of 62e7406: what a lifted copy is said to stop

26. **The lift line says a copy on file stops the lane here until
    `refusal.py --clear`, and a fetch started by hand here for 24 hours from
    when it was met** (`refusal.force(lift=)`, `pull_refusal`,
    `watchers/README.md`), not design_final §2.6's "the lane and every fetch
    here stop at it". That sentence is true only once `check()` stops at a
    GitHub record with a kind at any age (design_final §2.10, build plan
    commit 8 of design_final, 9 of the addendum), which is not built yet;
    until then a hand fetch passes such a copy after 24 hours. The commit
    that builds the any-age rule restores §2.6's sentence, and
    `_cloud_pull_lifted`'s assertion on it changes with it. Likewise
    `cloud_kit.json`, `ARCHITECTURE.md` and `refusal.py` now say nothing
    knocks yet; the commit that wires the knock says it does.
27. **Finding 7 of the review (the carry across a person's clear) changes
    no code**: DEVIATIONS 20 records it, and `_refusal_relapse` already
    pins the carry of a record noted within `RELAPSE_HOURS` of a lift
    whatever was cleared between (it removes the record and notes a new one).

## Commit 4: the knock child

28. **The knock asks through `snapshot_gencourt._OPENER`**
    (`refusal.no_redirect_opener()`, DEVIATIONS 25), not a new
    `_no_redirect_opener()`: one opener without any redirect handler, which
    H6 reads as `_OPENER.handlers`.
29. **C5's "a record 2 h old gives exit 4" does not hold under the hourly
    ladder**: a record noted at 08:27 is due at 10:27 (an hour's rung from
    its start, design_final's 16-hour first rung being gone). `_the_knock`
    tests "a knock 20 minutes before, in the same rung" instead, and the
    hourly caller's late-record cases are H11's (`_knock_settles`).
30. **Only a 200 lifts.** design_final §2.4 says "200"; another 2xx is a
    failed knock ("not the file"), the stricter reading of something it does
    not name.
31. **The knock reads its answer with its own judges** (`knock_error`,
    `knock_body`), design_final §2.4's table, not `classify()` alone:
    `classify()` calls a 503 "refused" before reading its body, and is
    unchanged. `refusal.unavailable()` gained `head=`, so the knock reads a
    body once. What the knock records (`said`) is this project's words -- a
    status number, a size, an exception's type -- never a server's reason
    phrase or body, so `person_line()` never carries one into an email.
32. **The gate's own `whose()` test is implied by `knock_due()`'s**
    (DEVIATIONS 19): the mutation that removes only the gate's survives
    `_the_knock`, and removing both is killed. Kept, as designed, like
    DEVIATIONS 11.
33. **The claim names no address** (`"url": ""`): `refusal.py` holds no
    literal General Court address (`_every_fetcher_checks_refusal` reads any
    script with one as a fetcher). `knocking()` writes the address into the
    claim it takes over, with the request's own time as `epoch` and the
    claim's as `claimed`, so the ladder counts the request.
34. **`--person-line` (the knock job's "What the refusal is now") reports
    only a record the chain names** (`person_line(tested=True)`), as
    `--knock-look` does: the addendum §6.1 says the knock workflow reports
    "a record it was testing"; §6.1's `person_line` paragraph states the
    restriction for the look only. The night (`person_alerts_of`, commit 5)
    reports every record.
35. **The look writes the person's line only where the hourly clock allows**
    (`knock_hours("hourly")`: the windows and their margin, for the knock's
    two minutes), not the settle rule, which is about which laptops may ask,
    not whether the bucket the look read is behind the night.
36. **A knock whose answer cannot be written down** (`knocked()` raising)
    stays "no answer" (a failed knock) and exits 2 for a block-type answer,
    1 otherwise, so the run that heard a refusal stops even when its record
    failed. A lost lock before the request, or a knock that cannot be
    written down first, exits 4: nothing was asked, and `--knock-unclaim`
    marks a claim "not asked". The child's own kill releases a lock it took
    before `os._exit(124)`.
37. **Held when `knock.yml` exists (commit 8)**: H3's two cron lines, H6's
    one invocation in the knock step, H7's two `if`s, and which steps set
    `GRANITE_KNOCK_BY`. `_the_knock` already holds that no code but
    `nightly.knock()` sets it, and no workflow line but a step env entry
    `GRANITE_KNOCK_BY: hourly` in `knock.yml`.
38. **H3 adds a merged-windows case** (Monday's weekly window running into
    the daily one, which `night_window()` gives as one span): the night's
    caller still starts at its own window's opening, a rule the moved-window
    sweep alone could not tell from a copy of 08:00.
39. **The look's `why` carries the settings in force**, or why they do not
    read, as the addendum's §10 step 5 wants the dev dry run's log to show.
40. **snapshot_gencourt's closing line** ("refusal.py holds every fetch for
    a day", design_final §16's drift) now says what stops at a refusal
    today: a hand fetch a day, the lane and GitHub's night until a person
    clears it. The commit that wires the knock (6) adds the knock to it.

## Commit 5: the third check and the switch

41. **Until the night knocks, the third check is told of a refusal the
    night could test** (`person_alerts_of` calls
    `person_line(untested=True)`). design_final §9 says that from this
    commit "every record that is a person's (which, until commit 6, is every
    record) emails through the third check"; but with the five lines in the
    workflows, the switch on and the secret set, `whose()` calls GitHub's own
    drop the night's, and the third check would read "up" over a refusal
    nothing will ever lift. So until commit 6 a record the night may test is
    a person's here, with the sentence "nothing in this build knocks for it
    yet". Commit 6 drops `untested`.
42. **The third ping comes first in "Tell Healthchecks how the night
    ended"**, after the exact-ref guard and before the step looks for
    `HEALTHCHECKS_URL` (whose absence ends the step), so a night with no
    night's check still tells the third one. design_final §2.9 gives the
    three cases, not their place.
43. **`person_alerts_of(v)` reads the record on file**, as `alerts_of()`
    does; `v` is the alerts' signature. A record that raises while being
    judged is said to be a person's (an alert must not stop the verdict).
44. **C16's "nothing else reads either"** is held as: no workflow line
    outside the five names any of them, and no Python file but `refusal.py`
    (and preflight) holds any of the five names as a literal. `cloud.py`
    names `NIGHT_KNOCK` only inside its sentences.
45. **`_workflows_secrets` runs on its mutants**, the addendum §8.4's way:
    its rules moved into `_wf_secret_problems()`, unchanged but for the one
    allowed line, `WF_PERSON_CHECK_LINE`. C16 (`_workflows_night_knock`)
    likewise carries nine mutants of its own.
46. **C11's "no knock date" for the day-0 alert** is held as the night's
    refusal line carrying no word "knock" at all: until commit 6 the
    night's alert is today's line, naming `clear-refusal`.
47. **A mutation of `knock_on()`'s settings test survives C11**:
    `whose()` reads the settings first and gives their sentence. The rule
    C11 holds is `whose()`'s (killed when removed); `knock_on()`'s own copy
    is held by `_cloud_lift`, where `cloud.knock_switched_on()` reads it.
48. **The operator checklist is not changed**: `reports/cloud/CLOUD_MOVE.md`
    is on the laptop, not in the repository. The owner's steps for the third
    check (D5) go into stage E's OWNER_STEPS.md.

## Commit 6: the night knocks

49. **Each of the knock's conditions lives in one place.** `main()` asks for
    the runner's night, not a New term run, and `night_tests()` (a record on
    file, no other fetch holding `archive/.lock`, `whose()` "night");
    `knock()` asks the dry run (`a.dry_run`, which `main()` already makes the
    workflow's `DRY_RUN` and a ref off main), `knock_due()` and
    `asking_left(KNOCK_MINUTES + EXPORT_MINUTES)`. design_final §2.3 lists
    them as one set; doubled, a condition removed in one place survives its
    check (DEVIATIONS 11, 32), and split this way C6 catches each.
50. **The knock and the export each take the night's lock.** `knock()`
    holds `refusal.hold("nightly")` around the child and lets go; the export
    takes it again a moment later, after `gc_quiet()` is read again, lock
    included. design_final §2.3 gives the knock and the held path each
    "under refusal.hold("nightly")". On GitHub's machine nothing else takes
    the lock between: one job in `gc-night`, and no lane.
51. **The day-0 alert names the night's own knock, not the hourly pattern**:
    "the night knocks once at its start, on each morning a knock is due, the
    next from <utc>, until <since + KNOCK_DAYS>, when the record is yours"
    (`nightly.knock_pattern()`), not `refusal.knock_schedule()`'s "one
    request an hour outside ...". Until `knock.yml` exists (build plan
    commit 8) only the night knocks, and an email promising hourly requests
    would be untrue were this the last commit. Commit 8 changes the
    sentence to `knock_schedule()`'s, as the addendum §4.3 has it. The
    docstrings say the same: "the hourly knock is to come".
52. **The night's alert carries a refusal the night tests only on a night
    that is not clean** (`refusal_alert()`): design_final §2.9's "only when
    it is a person's or the night was not clean". Until commit 7 every night
    under such a record builds nothing and is not clean, so the line stands
    every night of the outage, one email (Healthchecks writes on the change).
53. **The knock's line is the verdict's `knock` and a line on the run's
    page, not a warning of its own.** design_final §2.5 calls the clock's
    "not asked for: it is HH:MM UTC" a `clock_kind` warning; here it is said
    in `knock`, and commit 7's held line (`KIND_WEB_HELD`, which never holds
    the gate) carries it on a held night. The lift adds no warning kind: C6
    compares a lift night's kinds with an ordinary night's.
54. **`plain_why()`'s "deferred" sentence quotes the verdict's `knock`**, so
    the night's alert ("The night was not clean: ...") says what the knock
    did. design_final §5 names `plain_why` among the sentences to change.
55. **The lift night's one try is `if lifted:` after `if tries >= last:`**,
    with a line in `tried` (`EXPORT_ONCE_LIFTED`); design_final §2.3 puts
    the test "beside" it. Placed after, the order `_nightly_falls_back` pins
    (the database, then `last`, then `if tries >= last`, then the wait) is
    unchanged, and the break still comes before the wait.
56. **`run()` takes `env=`**, laid over the hold's variable as
    `{SQL_HELD_ENV: ...} | (env or {})`, so the pin on `run()`'s environment
    (`_nightly_falls_back`) reads it unchanged.
57. **`nightly.KNOCK_MINUTES` is `refusal.KNOCK_MINUTES`**: one number for
    the child's own kill and the parent's, where design_final §5 gives
    nightly a `KNOCK_MINUTES = 2` of its own. C13 holds them equal.
58. **Held for commit 7**: C6's database rows (here a knock not answered, not
    asked or not due ends in FETCH DEFERRED, as design_final §9 says of this
    commit), C11's held clean night (`warns_of()`'s held line), and C18's
    sequence 2 (sixteen days of database nights).
59. **C18 drives the third check's state from the files `--close` writes**,
    read as the ending step pings them (`_rings`), through a night driver of
    the checks' own (`_KnockNights`): the knock child there is the child's
    own gate, `knocking()` and `knocked()` in-process, with the answer the
    check gives; nothing is asked of anyone.

## Commit 7: the database while held (D3)

60. **C1's gate part is a check of its own, `_held_database_door`**, not
    rows in `_refusal_kinds`. That check needs only `refusal`; the door is
    `nightly.from_database()`'s, and a mutation of nightly's gate has to
    fail a check that loads nightly. It calls `from_database(held=True)` on
    fakes for every record `_refusal_kinds` holds to be a person's (and for
    `KNOCK_DAYS` typed wrong and sixteen days on): nothing asked, and its
    `tried` says a refusal is on file. It also holds the night's own drop
    without `held=True` shut, and the door open for it with `held=True`.
61. **`v["web"]` is set in `main()`, after the knock, by `web_state()`**, not
    in `knock()` (design_final §5). A night that does not knock -- not due,
    past the hours, a dry run -- is held all the same and needs the same
    line, so one place sets it for every night with a record on file or a
    lift. A held night's carries `last`, `by` and `until` beside the design's
    `{state, kind, since, knocks, next, lifted}`, for the held line
    (`held_line()`): the last knock and whose, and the day the record
    becomes a person's.
62. **DEVIATIONS 53's "the held line carries it" is held as two lines**: the
    held line (`KIND_WEB_HELD`) says when the next knock is due, and the
    run's page's "- the knock:" line (commit 6) carries the clock's "not
    asked for: it is HH:MM UTC". The held line does not repeat the clock's
    sentence; the run's page cuts a note at 300 characters.
63. **A dry run takes the held path**: it asks the database and builds, and
    never knocks (C6's dry-run rows hold both). design_final §2.3 step 3
    names `--runner`, not `--new-term` and no lock held; a dry run takes the
    database on an empty export today, and a held night is the same night
    with no export.
64. **The held night's later steps follow the database only when it
    installed**, as the export's path does (`rc == 0 or db_day`). The
    study committees' meetings, the term's data and the statutes are asked
    then. The bill requests and the lists are said "not asked for:
    <WEB_HELD_SAID>; the copy on file kept" then too. A held night whose
    database installed nothing builds nothing and says nothing of them;
    `plain_why()`'s held sentence says why, with the knock's line.
65. **No `db_open` variable**: `held_night()` is its own path (the export's
    loop is not entered), so it asks the study views, term data and
    statutes itself, which is what design_final §5's `db_open = not
    MARK.exists() or held` amounts to on that path. The export's block
    still reads `not refusal.MARK.exists()` for each, unchanged.
66. **`from_database(held=True)` writes its own first `tried` line**, "the
    export: not asked, because <because>", before the database's, so a held
    night's `tried` says the export was not asked. `because` also goes to
    `day_files.because` (design_final §5).
67. **`from_database()`'s SQL-host hold is renamed `sql_hold`**: `held` is now
    the parameter, the website's. Behaviour unchanged.
68. **Members.txt on a held night is the installed one**, its database note
    "the installed one: the website was not asked tonight" and its warning
    "Members.txt was not asked for, the website being held, so the installed
    one stays" (design_final §2.3's table: "not asked: the website is held").
    `tonights_members()` is not read even when the archive holds a
    Members.txt the website served earlier that day; C6's not-due row plants
    one, so that a held night reading it fails the check.
69. **Rule A is held by three guards, and C7's 311k fails only with the
    loop's two and the door's `held and` removed together**: the export loop
    breaks on anything but an empty export and on a refusal on file, and
    `from_database()` opens only with `held=True`, which the loop never
    passes. Any one left in place still stops the drop night before the
    database, so the mutation proof takes all three away.
70. **`_nightly_falls_back`'s pin on `from_database(` calls counts two**: the
    export loop's and `held_night()`'s, the second required to pass
    `held=True`. Its runs 310h (held, due later) and 311k (rule A) are new;
    310, 311, 311b and 317 and the direct call are unchanged and green.
71. **C14 is rows of `_nightly_weekly`**, as design_final names. Its held week
    leaves `preflight.py` (the week's own code checks, run as a child) out of
    the list of what was asked before comparing.
72. **The held `DB_NIGHTS_MOST` sentence says "the next knock is due from"**,
    the night's own next morning, and "the refusal becomes yours by". Until
    commit 8 there is no hourly knock to promise (DEVIATIONS 51).
73. **A held night counts `db_stopped` in `held_night()`**, by night as the
    export's path does: a guard's stop once a night, nothing after a night
    that installed.
74. **C18's sequence 2 is sixteen days of held nights, each `--runner` then
    `--close` read as the ending step pings them** (the addendum: it ends at
    16 days, not the fourth knock). The third check is up through day 15
    and down on day 16; the night's own check is up on held nights 1 to 6
    and down from the seventh, whose error names the website held.
75. **The checks' night driver (`_KnockNights`, commit 6) sets
    `GRANITE_CLOCK_UTC` in its own `night()`** as well as through
    `_KnockClock`. `_clock_fakes` reads each top-level harness that fakes
    `nightly.run` and runs `--runner` for an assignment of the clock in that
    harness itself, and failed on `_KnockNights` from commit 6 on; the
    stage's one full run found it, and it has a commit of its own after
    commit 7. `_KnockEnv` puts the variable back, so no check is left with
    the clock set.

## Commit 9 of the addendum (built before 8): the laptop tightening

76. **"A GitHub record with a kind" is `refusal.any_age()`: `machine ==
    "github"` and a `kind` key that is not null**, whatever the kind and
    whatever its `ref` or `dry` (design_final §2.10 says "any kind"). A dry
    run's drop, or GitHub's 403, stops a hand fetch at any age too: the
    stricter reading. `standing()` carries the rule, so `check()` and
    `refusal.py`'s status read it alike. cloud.py's decisions about
    *sending* a laptop record (`clear-refusal`'s check, `refusal_unsent`,
    pull's "IS NOT IN THE BUCKET" failure) still read its age
    (`hours_left`): they ask whether a record should go to the bucket, not
    what it stops here. Their sentences that said "hand fetches here are not
    stopped by it" now come from `cloud._stops_here()`, which says so only
    where it is true.
77. **`--clear` writes `archive/refusal-cleared.json` before it removes the
    record, and clears nothing (exit 1) when the note cannot be written.**
    The addendum §7 item 2 gives the file, not the order; in the other order
    a failed write would leave the laptop free to ask with the bucket's
    record unread.
78. **On a stood-down laptop `--clear` writes the note even when no record
    was on file**, as "also writes" reads: the next fetch reads the bucket
    first all the same.
79. **The note's time is refusal's clock** (`_utc()`, `GRANITE_CLOCK_UTC`
    when set, as every gate reads it); a note that does not read counts as
    a clear after every read, so the next fetch pulls first; and a read in
    the same second as a clear is no read (`cleared >= read`).
80. **"Stood down" for `--clear` is `_governing()`** -- the stand-down file
    beside the record, which `gc_turn()` reads -- not `stood_down()`'s file
    in the working folder: the same there, and a check's folder is governed
    by itself, never by the laptop it runs on. The line naming
    `clear-refusal` for the bucket's copy follows it too.
81. **DEVIATIONS 26 is closed.** `force(lift=)`, pull's two lift lines and
    `watchers/README.md` say design_final §2.6's sentence again: the lane
    and every fetch here stop at a lifted copy until `refusal.py --clear`.
    `_cloud_pull_lifted` asserts that wording, and that such a copy is
    `any_age`.
82. **C10's pull is `cloud.pull_refusal()` on a folder bucket, with the
    read written into `archive/cloud/pull.json` by the check, marked `r2`**
    as `cmd_pull` records a read of R2 -- the addendum's "the read marked r2
    as the test's fake". `cmd_pull` itself refuses a bucket that holds no
    night (`bucket_is_the_nights`).
83. **`check()`'s stop for a record the night may test names the switch**:
    "to check or clear it sooner yourself, first set the GitHub variable
    NIGHT_KNOCK to off" (addendum §7 item 4), from this commit, since a
    hand fetch now meets such a copy at any age.

## Commit 10 of the addendum (built before 8): netcheck

84. **Test 8 is dropped, not relabelled**: seven requests, not eight.
    design_final §5 allows either; it asked the fourth test's page over the
    fourth's HTTP version, so dropping it is one request fewer at an address
    that may be blocking, and tells nothing less.
85. **netcheck's verdict reads its own answers through `answered()` and
    `through()`**: a 2xx that is not the block page (`refusal.BLOCKED`) gets
    through; a 3xx is "a redirect, not the page"; 4xx and 5xx "the server
    ANSWERED, and said no", for urllib's HTTPError and a raw connection's
    status alike (the raw socket never raised, so its 403 counted as
    through). A line above the verdict counts the answers that said no.
86. **netcheck asks through two seams a check can fake, `URLOPEN` and
    `CONNECTIONS`**, and C15 also makes the process's sockets refuse to
    connect while it runs, so a seam a change bypasses fails the check
    rather than asking the General Court.
87. **"A record GitHub may be testing" is `refusal._its_own()`** -- whose()
    conditions 1 to 5: the addendum's machine, kind, ref and dry, plus a
    `Retry-After` within `RETRY_AFTER_MOST` (a longer one is a person's,
    which no knock tests). A copy the knock has already lifted still asks
    for `--knock-stopped`: the laptop does not read the bucket's lifts
    there, the stricter way.
88. **Stood down, for netcheck, is `refusal._governing()`**, as `gc_turn()`
    reads it (DEVIATIONS 80), and both refusals exit `STOOD_DOWN` (4),
    having asked nothing.
89. **Until the hourly knock exists, netcheck's sentence names only the
    night's test**: "set the GitHub variable NIGHT_KNOCK to off, wait until
    the Actions tab shows no night running, then run python3 netcheck.py
    --knock-stopped". Commit 8 adds the knock workflow to it, as the
    addendum §7 item 3 words it.

## Commit 8 of the addendum (built after 9 and 10): the hourly knock

90. **`knock.yml` is the addendum's §3.1 as written, with two additions.**
    `defaults: run: shell: pwsh` at the top, as `nightly.yml` and
    `weekly.yml` say (windows-2022's default already; every step of the
    ubuntu jobs names bash). And the elided part of `quiet` (§3.4 steps 2 to
    4) is one inline standard-library Python, `decide.py`, written by a
    quoted heredoc and run twice: `open` lists the ids of the runs not
    completed (this one aside), each list's `total_count` checked against
    what came back; `quiet` reads each open run's jobs and decides. Each
    list is saved as `<workflow>.json` (`nightly.yml.json`, not the sketch's
    `nightly.json`). Every `gh api` call and both runs of `decide.py` end
    `|| busy "..."`, and H2 holds that by the text of each line as well as
    by running `decide.py` on canned answers.
91. **The span and the open hours of `hourly_silent()`.** The eighteen hours
    are from the daily window's close (13:30) the day before to this
    morning's anchor (`knock_anchor()`'s time of day, 07:30), whatever time
    the night reads it. An hour is open when, at its :47, `knock_due()` was
    true **with only the knocks made by then**, `knock_hours("hourly")`
    allowed it (so Monday's weekly window counts too), and the settle rule
    held by the record's own `epoch`. The filter is there because the night
    reads the silence in `web_state()`, after its own knock at its start
    (the addendum says "read by the night at its start"): unfiltered, the
    morning's own knock would make every hour of the night before look not
    due. H12's nights fail without it (revert proof).
92. **The sentence adds the count and the path**: "the hourly knock has not
    run since <utc>, its last entry | the refusal began, <utc>: none in the
    <n> hours before this morning it could have knocked.
    .github/workflows/knock.yml may be disabled, paused by GitHub, or
    without its read-only R2 key; the night still knocks once each morning".
93. **The first morning's alarm comes from the verdict's `web`**:
    `web_state()` keeps `silent` and `silent_new` (it holds this morning and
    did not, `now` less a day), and `Night.alarms()` adds the sentence when
    the night is held and `silent_new`. The alarms it had before are
    `data_alarms(v)`, a module function, because an existing check calls
    `Night.alarms` on a bare namespace. After the first morning the sentence
    is its own line in `warns_of()`, after the held line, not inside it, and
    not in `Night.warned()`: there it would be a warning kind of the night's,
    which reaches the review gate (H12 holds it out of the reasons).
94. **An alarm-only night's email says the alarm.** `alerts_of` gave such a
    night `plain_why()`'s "The night stopped before it recorded what it
    did", which is untrue of a night that built and published. A night not
    clean only for its alarms now reads "The night was built, with an error
    to act on: <alarms>. The build was not held back for it." This changes
    the email for `DB_NIGHTS_MOST`'s and the fallback's alarms too.
95. **`DB_NIGHTS_MOST`'s held sentence does not say "within the hour".**
    It is read at the night's end, about 09:30 UTC, inside the night's
    hours, where no hourly knock runs before 13:47; so it keeps "the next
    knock is due from <utc>" and adds ", and one an hour after that outside
    the night's hours until <utc>" while the hourly rungs last
    (`web["hourly_until"]`), and nothing after.
96. **The day-0 email's pattern is `refusal.knock_schedule()`** (§4.3), and
    `nightly.knock_pattern()`, the night-only pattern, is gone; C11's
    expected words follow it ("one request an hour outside 07:30-13:30
    UTC", "and one from the night itself at its start"). The email and
    `refusal.check()` name disabling the knock workflow beside
    `NIGHT_KNOCK`; netcheck's refusal names it too (DEVIATIONS 89 closed),
    and to wait for no knock run as well as no night.
97. **Fixtures that model knock.yml running.** `_nightly_falls_back`'s 310h
    record and C18's sequence 2 (sixteen held nights) get an hourly claim
    marked "not asked" between nights, as the workflow running would leave;
    without one the silence alarm rightly makes those nights not clean.
    H12 has the mornings without one.
98. **`_workflows_permissions` is amended, not "already allows"** (§3.2):
    its `actions: read` shape was `nightly.yml`'s `started` alone. It is
    now a table, `WF_ACTIONS_READERS`, of (workflow, job): `nightly.yml`'s
    `started` and `knock.yml`'s `quiet`, each allowed only `gh api -X GET`
    of runs and their jobs (a `gh api` with `-f` and no `-X GET` would
    POST). The two read-only secrets join `WORKFLOW_SECRETS`.
99. **`_workflows_dry_runs_wait` decides "can a dry run's gc-night job
    run" by evaluating each gc-night job's `if` as GitHub would** for every
    kind of dry run in `WF_RUNS`, on a first attempt, over the values
    ("true", "false", "0", "1", "success", "") of each `needs` output it
    reads (`_wf_job_can_run`). `WF_RUNS["knock.yml"]` carries the schedule
    line as an `event.schedule` box, which `_wf_run_ctx` reads as
    `github.event.schedule`.
100. **H1 carries H6's and H7's halves in the workflow**: no job but the
     knock runs `snapshot_gencourt.py`, once, in no loop; and the knock job
     runs only on a first attempt. Their halves in `refusal.py` are stage
     C's. H3's cron half (`_wf_knock_cron_problems`: the hourly line at
     `refusal.HOURLY_MINUTE`, never :00, :17 or :30, the daily line
     keepalive's alone) is shared by `_knock_hours` and H8.
101. **H8 also runs `src/ops/cloud.py --help` in the sparse tree**, beside
     `refusal.py --knock-look --help`: state-down is look's other script.
102. **`requirements-r2.txt`'s versions and hashes are this machine's, and
     its install on windows-2022 is unproved.** No `pip download` from PyPI
     was allowed in this stage. The seven are the set installed together in
     this machine's Python 3.14 (boto3 1.43.103, botocore 1.43.113,
     s3transfer 0.19.2, jmespath 1.1.0, urllib3 2.8.0, python-dateutil
     2.9.0.post0, six 1.17.0), closed by their own declared requirements;
     each is a py3-none-any or py2.py3-none-any wheel. The hashes are uv's
     cached PyPI index entries for those wheel files; four of the seven
     were checked against the wheel's own bytes in pip's cache. pip's
     offline `--no-index --dry-run --require-hashes` parsed the file and
     stopped at resolution, having no wheels to install. The dev dry run of
     knock.yml (§10 step 5) is the proof.
103. **H10, the knocks-on-file reader, is not here**: the addendum's build
     plan puts it in commit 11 with the docs.

## Commit 11 of the addendum: the docs and the knocks' record read (H10)

104. **H10 is left off the night's own checks** (`NOT_ON_THE_NIGHT`, beside
     `_nightly_logs`). The addendum says a data check "not in `--code`", but
     every data check also runs on the night under `--built`, where a
     failure holds the site for approval -- or, as a warning, adds a kind
     the gate has not seen, which holds it too. A ladder that failed is no
     reason to hold a sound site, and nothing in the design routes H10
     there. `_knocks_on_file_reader` asserts it stays off.
105. **So H10 reads real data almost nowhere yet.** It reads
     `archive/knocks.json` (`refusal.knocks_file()`), as designed, and
     skips without one. The laptop, where a full preflight runs, holds none:
     its `pull` reads the bucket's `state/knocks.json` for lifts and keeps no
     copy. GitHub's machine holds one after state-down, but runs only
     `--code` and `--built`. **A later step, for the owner:** `pull` keeping
     a copy (say `archive/cloud/knocks.json`, never `archive/knocks.json`,
     which `refusal.py` reads as its own) for H10 to read. It is not built
     here, because it adds a write to `pull`, which the design does not.
106. **"None with a dry ref" is judged by the chain's record, not the
     entry.** A knock entry carries no ref. A chain's record is the lifted
     entry's own `text`, or the record on file when `current` names it by
     sha. A chain holding a knock for a record `refusal._its_own()` refuses
     (a dry run's, another ref's, the laptop's, a kind that said no, a long
     Retry-After) is a finding. Where `current`'s record is not on file
     (the laptop), this and the settle rule are not judged, and the summary
     says so.
107. **A knock is judged at its own time and at `KNOCK_MINUTES` before.**
     `knocking()` stamps the request, which follows the gate's reading by
     less than the child's two minutes. A request whose two minutes crossed
     into the six-hour phase, or past the cap, was kept by the gate's
     reading. The rule for rungs, gaps and the cap allows that; the window
     and the settle rule need no allowance (the gate read them at the
     request's two minutes ahead, and the last window end only grows).
108. **Only the last `KNOCKS_JUDGED_DAYS` (30) days are judged.**
     `knocks.json` keeps every knock and lift for good. Judging all of them
     would fail the data checks for ever once one finding had been read and
     dealt with, and CLAUDE.md has a session fix preflight first. Thirty
     days is about as long as the bucket keeps the night's logs to read a
     finding by.
109. **The settle rule judges the hourly knocks made since the record's own
     time.** Knocks a relapse carried were made for the earlier record, and
     are judged with it in its `lifted` entry. A request is any entry but
     one marked "not asked", a "claimed" one included, as `chain()` counts.
110. **The settings are this process's.** The repository variables are
     GitHub's; the summary names the settings it judged by and says to set
     the same here where they differ.
111. **design_final's log reader is not built.** Two knock lines on a date,
     a dry run's knock line, and a knock outside 08:00-11:18: H10 replaces
     it (addendum §10 item 11), on the state file rather than the logs.
112. **H10's reader runs under `--code` too**, as `_knocks_on_file_reader`.
     It runs on documents whose answers are known: a sixteen-day ladder
     kept by `refusal.py`'s own writers, read as tested and as lifted, and
     each sign beside its near miss. It also runs the data check on a
     record of its own, as `_nightly_logs`' reader is held under `--code`.
113. **ARCHITECTURE's alerts sentence**, "its recovery is the sign it was
     cleared", gains "or lifted by the night's knock" (design_final §7). The
     drift the design names is mended: a night the gate holds for approval
     went to the warnings' check on 22 October 2026 (c310ee1,
     `held_for_approval()` in `warns_of()`), and a refusal the night tests
     reaches the night's alert only on a night that is not clean.
     `src/ops/README.md` names the knock workflow among `cloud.py`'s callers,
     and the three refusal commands. The rest of design_final §7 and
     addendum §9's tables went in with the commits that changed the
     behaviour. The operator checklist is on the laptop; its D5 steps are
     in `OWNER_STEPS.md`.

## After the review of d7d64bb: an answer not written down is a person's

114. **DEVIATIONS 36 is replaced.** A knock answered no whose answer could
     not be written down was left "no answer", a failed knock: the night
     took the held path and asked the database, nothing told the third
     check, and the hourly knock asked again an hour later. Now:
     - the child tries the write a second time (`_answer_down`); if that
       fails too it exits 2 for an answer `knocked()` would have made a
       person's (a block-type answer, or a 503 asking longer than
       `RETRY_AFTER_MOST`) and 1 for any other, the entry left "no answer";
     - **a knock entry still "no answer" `KNOCK_JOB_MINUTES` after it was
       made is an answer lost, and a person's** (`whose()` condition 6,
       beside the lost claim), from any run, this one's included: a run
       longer than `KNOCK_JOB_MINUTES` has written its knock's answer long
       before;
     - so whatever kills a knock with no answer writes the answer "dropped"
       over its "no answer", as a killed knock was designed to count (a
       failed knock): the child's own kill (`_knock_killed`, under a lock
       the answer's own write holds, so the two never both write), and the
       night after `RUN_KILLED`. The addendum's C5 and H7 say a killed knock
       "leaves 'no answer'"; it now leaves "dropped". A kill that cannot
       write leaves "no answer", which becomes a person's: the safe way;
     - the night reads the knock's exit 2 itself (`knock_said_no(v)`, the
       verdict's `knock` beginning `KNOCK_SAID_NO`): no held path, no
       database, `web` a person's, the night's alert the person's sentence
       naming `clear-refusal`, and `person_alerts_of` the person's line
       (`refusal.person_line(said_no=...)`) that night, before `whose()`
       can say so;
     - knock.yml's knock step puts its exit in its outputs (`rc=`), and
       "What the refusal is now" passes it as `--knock-rc`: a 2 the chain
       does not show writes the person's line (the /fail that follows) and
       exits 1, so the job is red. The bucket holds the "no answer" entry,
       which the next look reads as a person's.
     The reviewers' simplest option, a second write by another route (for
     example the record rewritten as "refused"), is not built: it would
     write beside the file that has just failed to take a write, and the
     "no answer" rule above needs no second file.
115. **DEVIATIONS 25 is closed: the night's other two fetches follow no
     redirect either.** `src/fetch/gc_web/fetch_lsrs.py` (`get()` and
     `post()`, the search page and its postback) and
     `src/fetch/gc_web/fetch_calendar_archive.py` (`_get()`) keep a
     `refusal.no_redirect_opener()` as `_OPENER`, as the snapshot and the
     committee pages fetch do. A 3xx to the bill requests ends the run with
     status 2 and a refusal of the kind "refused" on file; a 3xx to the
     night's listing (`--listing`, `listing()`'s `ask`) is `Stop(2)` with the
     same record. The laptop's drain and `--discover` share `_get()`, so
     they follow no redirect either; they read a 3xx as `classify()` reads
     it, a failed request (two in a row stop the drain), and not as a
     refusal: they are not the night's, and nothing about them was found.
     `_night_fetchers_no_redirect` drives all four fetchers against a server
     of its own on 127.0.0.1. Nobody has seen either page answer with a
     redirect: if the postback or an index page did so in the ordinary way,
     the first night after this lands would record a refusal the night
     cannot test (kind "refused" is a person's), and the email says so.
116. **One night knock a morning** (`knock_gate()` condition 8). The
     ceiling for_owner states, 96 requests a chain and about 19 a day,
     counted the night's knock once a morning, but nothing held the night's
     caller to it: in the hourly phase a re-run, a run by hand or the
     double night knocked in a rung of its own, 100 knocks and 22 in a day
     in the ladder (the reviewers' simulation, and `_knock_ladder`'s with
     the rule taken out). The gate now refuses the night's caller when the
     chain holds a knock `by` "night" since today's window opened -- the
     reviewers' rule -- and also when the record itself was noted since
     then: only a night asks in that window, so the drop that morning was
     the night's request. Without that second half a re-run on the morning
     of the drop knocks once more than the ceiling counts (95 knocks in the
     ladder, 97 requests). The ladder with the night asking at 08:23:40,
     09:23:40, 10:23:40 and 11:10 every morning is 94 knocks, at most 19 in
     a day.
