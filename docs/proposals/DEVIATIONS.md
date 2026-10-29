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
    can take the same one and meet H6 as written. **Not changed here:** the
    night's other two General Court fetches, `fetch_lsrs.py` (`get()`, its
    two `urlopen` calls) and `fetch_calendar_archive.py --listing`
    (`_get()`), still follow a redirect. They ask only on a night with no
    refusal on file, after the export answered whole; the reviewers' finding
    named the snapshot and the committee pages, and these two are left for
    the next stage rather than changed unreviewed.
