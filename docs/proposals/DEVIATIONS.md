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
