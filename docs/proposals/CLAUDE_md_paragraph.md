# CLAUDE.md: the proposed wording, for the owner to apply

CLAUDE.md is the owner's file, and nothing on this branch changes it. These
are the changes the approved design asks for (addendum §9, design_final §7),
checked against the code as built on `feat/outage-recovery`. Each one says
where it goes and what it replaces. Where the addendum's text no longer
matches the code, the change is listed after it, with the reason.

They belong in the commit that merges this branch to `dev`, or the next one.
Until then the current paragraph understates nothing that is unsafe: it says
that every refusal is a person's to clear. On `main` that stays true while
`HEALTHCHECKS_PERSON_URL` is unset, because the night tests nothing itself
without it.

---

## 1. Replace "A refusal outlives the run that met it" (CLAUDE.md lines 74-79)

The paragraph as it stands:

> **A refusal outlives the run that met it.** `refusal.py` records one in
> `archive/refused.json` and holds the fetch lane for 24 hours. It exists because
> a drain that met two 403s stopped itself correctly, and a chained run started
> asking the same address for a docket twelve seconds later. Clearing it is a
> person's decision: `python3 refusal.py --clear`, after `netcheck.py` has said
> what kind of refusal it was.

The proposed paragraph:

> **A refusal outlives the run that met it.** `refusal.py` records one in
> `archive/refused.json`, with what kind it was. It exists because a drain that
> met two 403s stopped itself correctly, and a chained run started asking the
> same address for a docket fifty-four seconds later. The lane, and GitHub's
> night, stop at a refusal for as long as it is on file. A fetch started by hand
> here stops for 24 hours, and for as long as the refusal is on file if GitHub's
> machine met it and wrote down its kind. One kind is the night's to test, by
> the person's decision of 29 October 2026: two dropped connections, timeouts,
> or a 503 that is not the firewall's page, met by GitHub's own night on
> `main`, not a dry run. That night ends as before. For up to sixteen days the
> nights after build from the General Court's database. Meanwhile GitHub asks
> the website one request at a time, for `dynamicdatadump/Counties.txt`: once an
> hour for the first two days and every six hours after (the repository
> variables `KNOCK_HOURLY_HOURS`, `KNOCK_EVERY_HOURS` and `KNOCK_DAYS`), from
> `.github/workflows/knock.yml` outside the night's window, and once from the
> night itself at its start. Never two in one hour or span; never beside a
> night, a weekly or a dry run. Any answer that is the file lifts the refusal
> (moved into `archive/knocks.json`). After the night's own knock lifts it,
> the export is asked once that morning; after an hourly one, the full fetch
> waits for the next night. For a week after a lift, one dropped connection
> ends the export. Everything else is a person's to clear, as it always was,
> and stops the database too:
> - a 403, a 429, the firewall's page or a redirect, on a night or to that
>   request;
> - sixteen days;
> - a fourth relapse;
> - a knock whose answer never reached the bucket, or was never written down;
> - the switch turned off, or a setting typed wrong;
> - any refusal met on this laptop or by a dry run;
> - any refusal without a kind, which is every one written before this
>   change.
>
> To clear one: `python3 src/ops/cloud.py clear-refusal` for the night's, and
> `python3 refusal.py --clear` here, after `netcheck.py` has said what kind of
> refusal it was. While GitHub may be testing one, set the variable
> `NIGHT_KNOCK` to `off` (or disable `knock.yml`) **before** netcheck or an
> early clear, so that two machines never ask at once. netcheck refuses on the
> laptop until told so (`--knock-stopped`), and `--clear` here makes the next
> fetch pull the bucket first. The Healthchecks check `HEALTHCHECKS_PERSON_URL`
> emails the moment a refusal becomes a person's. Nothing tests a refusal by
> itself unless that check is set. The repository variable `NIGHT_KNOCK` set to
> anything but `on` turns the testing off; unset, the workflows read it as
> `on`. Starting `knock.yml` by hand asks the General Court too, and is a
> person's to do.

**Where this departs from the addendum's text, and why:**

1. **"if GitHub's night met it" became "if GitHub's machine met it and wrote
   down its kind".** `refusal.any_age()` stops a hand fetch at any age for a
   record with `machine` "github" and a kind (DEVIATIONS 76). That covers a dry
   run's record too, and leaves out a GitHub record from before this change,
   which has no kind and still stops a hand fetch for 24 hours.
2. **"the full fetch waits for the next night" is said only of the hourly
   lift.** When the night's own knock lifts a refusal, the night asks the
   export once that same morning (`EXPORT_ONCE_LIFTED`, DEVIATIONS 55).
3. **"unless that check is set and the repository variable NIGHT_KNOCK is
   `on`" is said the other way round.** The three workflows read an unset
   `NIGHT_KNOCK` as `on` (`vars.NIGHT_KNOCK || 'on'`). As written, the addendum
   suggested the person had to set it on; they have to set it off to stop it.
   for_owner says the same ("the GitHub variable NIGHT_KNOCK set to off").
4. **The switch off and a setting typed wrong are listed among a person's
   refusals.** `whose()` makes the record a person's in both cases
   (`knock_on()`, `knock_settings()`).
5. **`<date>` is 29 October 2026**, the owner's "defaults" to D1-D6. "Any record
   from before `<date>`" is said by its cause: a record without a kind.
6. **The list of a person's refusals is a bulleted list**, not the addendum's
   one sentence between dashes, so it reads more easily. The words are the
   same.
7. **Two errors in the current paragraph are corrected, as design_final §7
   names them.** "twelve seconds" is fifty-four: `refusal.py`'s docstring
   says "Fifty-four seconds later". And the lane holds at any age, not for 24
   hours (`gc_lane.py` stops at any refusal on file).

## 2. Add a sentence to the `fetch_*_db.py` paragraph (CLAUDE.md lines 92-98)

After "...a different problem with a different cause.", add (design_final §7):

> The night reads that host by itself, for sixteen days at most, while a
> refusal it is testing stands, and never while one a person must clear stands.

## 3. Add to "Branches, the nightly and the kit" (after CLAUDE.md line 292)

After "...Anything the build reads that git does not hold must be on that
list.", add (addendum §9):

> `knock.yml` runs every hour and does nothing unless the bucket holds a
> refusal the night is testing; then it asks the General Court one small file
> at most (see *A refusal outlives the run that met it*).

## 4. Noticed while writing these; not in the design

These are offered for the owner to judge. Nothing depends on them.

- **CLAUDE.md line 61-62**, "`python3 netcheck.py` diagnoses a refusal without
  making things worse". This holds once nothing else is asking. While GitHub may
  be testing a refusal, it holds only after `NIGHT_KNOCK` is off; the paragraph
  in 1 says so. A clause here, "-- once nothing else is asking (see *A refusal
  outlives the run that met it*)", would keep the two in step.
- **CLAUDE.md line 119-120**, the guard "makes the person answer for what needs
  their word (publish, `main`, a fetch, wrangler, credentials)". If the D6 rows
  in `guard_rows.md` are applied, the list could add "clearing or sending a
  refusal, netcheck, re-running or cancelling a GitHub run".
