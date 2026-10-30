# The owner's steps: the night that heals itself

What only the owner can do, in order, for `feat/outage-recovery`. It follows
the approved design (`design_final.md` §8, the hourly addendum §6.2 and §10)
and what the owner was told (`for_owner.md`). Nothing here has been done for
you: no setting, secret or check was made, no workflow was started, and
nothing was pushed.

Until steps 2 to 4 are done and the branch is on `main`, nothing changes.
Even on `main`, the night tests nothing itself while `HEALTHCHECKS_PERSON_URL`
is unset; every refusal stays yours, as today.

---

## 1. Now, and not part of this branch: clear the refusal standing since 29 October

Decision 1. That record has no kind, so nothing in this branch will ever
lift it. On the laptop:

1. `python3 netcheck.py`. Read its table, not its last line.
2. `python3 src/ops/cloud.py clear-refusal`.
3. `python3 refusal.py --clear`.

## 2. The "a refusal is yours" check (D5, step 5.1)

1. **In Healthchecks, Add Check.**
   - Name: `a refusal is yours`.
   - Description: "Pinged by the nightly at its end (up, or /fail when a
     General Court refusal is a person's) and by the knock workflow (/fail
     only). Down means a person must act; the email's body says why."
2. **Schedule: Simple. Period 1 day. Grace 1 day.**
   - The night pings it once a day, normally about 09:30 UTC. GitHub has
     started nights 5 to 7 hours late, so two pings can be about 31 hours
     apart.
   - The knock workflow only ever sends `/fail`, so it never keeps the
     check up.
   - With 1 + 1 days, the check goes down by silence only after two days
     with no night reporting. The night's own check will have emailed
     first. An email from silence means the night stopped reporting, not
     that a refusal is yours: the `/fail` emails carry a body, and a silence
     email does not.
   - The default grace of an hour would email whenever a night ran late.
3. **Integrations:** your email on, as for the other checks.
4. **Copy the check's ping URL** (`https://hc-ping.com/...`).
5. **In GitHub:** the repository → **Settings → Secrets and variables →
   Actions → Secrets → New repository secret**. Name:
   `HEALTHCHECKS_PERSON_URL`. Value: the URL.
   - It must be a **repository** secret, not an environment's.
     `knock.yml`'s jobs and the weekly have no environment, and a
     workflow-level `env` cannot read an environment's secrets.
   - The workflows hand `nightly.py` and `refusal.py` only "set" or "none"
     (`NIGHT_PERSON_CHECK`), never the address.

## 3. A read-only R2 key for the hourly look (D5, step 5.2)

1. **In Cloudflare: R2 → Manage R2 API tokens → Create API token.**
   Permission **Object Read only**, applied to the kit's bucket only.
   *A guess:* these menu names, and that the account allows a token scoped
   to one bucket and read-only. The design's writers could not see the
   account.
2. **In GitHub, two more repository secrets**, the token's two values:
   - `R2_READ_ACCESS_KEY_ID`
   - `R2_READ_SECRET_ACCESS_KEY`

   The account id and the bucket name are the secrets already there
   (`R2_ACCOUNT_ID`, `R2_BUCKET`).
3. Without this key, `knock.yml`'s look says "No read-only R2 key
   (R2_READ_ACCESS_KEY_ID, R2_READ_SECRET_ACCESS_KEY): no hourly knock." and
   looks no further. The night still knocks once each morning. The first
   morning the hourly knock could have run and did not, the night says so
   once, as an error on its page and one email through its own check. So
   this key is needed for the hourly knock, not for safety.

## 4. The settings: repository variables (all optional)

GitHub → the repository → **Settings → Secrets and variables → Actions →
Variables**. Leave any of them unset for its default.

| Variable | Unset means | Allowed values | What it does |
|---|---|---|---|
| `NIGHT_KNOCK` | `on` | `on` or `off` | The off switch. Anything but exactly `on` turns all testing off; anything but `on` or `off` is also reported as typed wrong (below). A refusal being tested becomes yours, with one email |
| `KNOCK_HOURLY_HOURS` | 48 | a whole number of hours, 0 to 384 | How long after the refusal the knocks are hourly |
| `KNOCK_EVERY_HOURS` | 6 | 1, 2, 3, 4, 6, 8, 12 or 24 | The knocks' spacing after that |
| `KNOCK_DAYS` | 16 | a whole number of days, 1 to 16 | When the refusal becomes yours at the latest |

A value outside these, such as "48h", " 48", "-1", 17 days, or 5 hours a
rung, turns testing off. The night's warnings check
(`HEALTHCHECKS_WARN_URL`) then emails you, naming the variable, and says
so every night until it reads, whether or
not a refusal is on file. A refusal on file meanwhile is yours, and the "a
refusal is yours" check emails you too. To stop only the hourly knock: **Actions → knock →
"..." → Disable workflow**.

**Before you check or clear a refusal early yourself**, set `NIGHT_KNOCK`
to `off` (or disable the knock workflow) and wait until the Actions tab
shows no knock and no night running. A knock job lasts 15 minutes at most.
On the laptop netcheck then needs `--knock-stopped`. Two machines asking at
once is how the second block happened.

---

## 5. Landing

The order of design_final §8, with the addendum's step 5.

1. **1 November: the release (dev → main).** Nothing of this branch is in
   it.
2. **`feat/night-clock` merges to `dev`** and goes live on its own approval.
   This branch is built on it, and has `dev` merged in up to `cd8147f`.
3. **This branch merges to `dev` only after night-clock is in `dev`.** It is
   not pushed. The person (or a session on the person's word) pushes it and
   opens the merge.
4. **On `dev`:**
   1. `python3 preflight.py --code` in full, and `python3
      src/ops/handoff.py`.
   2. **A listing of the bucket's `state/` before the dry runs**, to compare
      after.
   3. **One nightly dry run on `dev`** (Actions → nightly → Run workflow,
      branch `dev`). It cannot exercise a knock or a lift, by design, and
      nothing should provoke a refusal to test one. Its log and the bucket
      must show:
      - no knock: no line "the knock:" at all, or "the knock: not asked: a
        dry run knocks nothing, and lifts nothing" if a refusal is on file;
      - no lift, and `state/knocks.json` neither sent nor changed (a dry run
        never sends it, `cloud.DRY_NEVER`);
      - `NIGHT_PERSON_CHECK: set` among the `env:` lines GitHub prints at the
        head of the night's steps, once step 2 is done. This confirms the
        design's guess that `${{ secrets.X != '' && 'set' || 'none' }}`
        works at the workflow level. `none` there with the secret set means
        the expression does not, and the testing would stay off.
   4. **One dispatch of `knock.yml` on `dev`** (Actions → knock → Run
      workflow, branch `dev`). It is a dry run by its branch. Its title reads
      "knock (dry run: not main)", and it waits in `knock-dry-runs`, never in
      `dry-runs`. Its log must show:
      - in the `look` job (Linux), the step "boto3 and its dependencies, each
        by its hash" installing from `requirements-r2.txt` with
        `--require-hashes`, and succeeding;
      - the step "Read the state files from R2, with a key that cannot
        write" running `cloud.py state-down` with the read-only key (not
        "No read-only R2 key"), once step 3 is done;
      - the line "the knock's look: ..." saying whose the record is ("no
        refusal is on file", or the refusal and whose it is), and the
        settings in force ("the settings: one an hour for 48 hours from the
        refusal, then one in each 6-hour span, for 16 days" at the defaults),
        and "no hourly knock now: a dry run knocks nothing ...";
      - `NIGHT_PERSON_CHECK: set` in the steps' `env:` lines;
      - the jobs `quiet` and `knock` **skipped**, and the look's step "Tell
        the 'refusal is yours' check ..." skipped too (its `if` asks
        `DRY_RUN` false);
      - afterwards, the bucket's `state/` listing the same as before.

      **Not proved by this:** the knock job's install on Windows. A dry run
      never runs the knock job, so its first Windows install is on `main`.
      `requirements-r2.txt`'s hashes are for pure-Python wheels, and four of
      the seven were checked against the wheels' own bytes. But no `pip
      download` from PyPI was allowed in the build (DEVIATIONS 102). Proof
      before `main`, if you want it, on the laptop (PyPI, not the General
      Court):
      `pip download --only-binary=:all: --platform win_amd64 --python-version 3.14 --require-hashes -r requirements-r2.txt -d %TEMP%\r2-wheels`.
      If it still failed on `main`, the knock job would fail before its
      claim: a red run, no request.
5. **Steps 2 and 3 before the merge to `main`.** Without the third check
   the merge changes nothing: every refusal stays yours, as today.
6. **To `main` only on your word.** It is a release for the gate, so it needs
   a clean dry run of the same commit within 48 hours, or your approval.
7. **After the merge:**
   - `knock.yml` starts at the next :47. With nothing on file each run ends
     after its look. The Actions tab gains about 25 short green runs a day:
     24 hourly and one keepalive.
   - **The morning after**, the "a refusal is yours" check shows "up",
     pinged by the first real night. If it still says "new", the URL is
     wrong. The method then believes the check is set while nothing
     arrives, so set `NIGHT_KNOCK` to `off` until it is fixed.
   - The first real exercise is the next real drop.

## 6. Yours to apply: the configuration (D6)

- `docs/proposals/CLAUDE_md_paragraph.md`: the CLAUDE.md wording, checked
  against the code as built.
- `docs/proposals/guard_rows.md`: ask before `cloud.py clear-refusal`,
  `send-refusal`, `netcheck.py`, `gh run rerun` and `gh run cancel`, with
  the rows preflight's `_assistant_guard` gains in the same commit, and
  what the guard's `decide()` says today and with them. It also lists two
  `gh api` forms that post past the guard today.

## 7. Open, and said so

- **The Windows install of `requirements-r2.txt`**, above (step 5.4).
- **H10** (`_knocks_on_file`, the reader of `knocks.json`) skips on the
  laptop, which holds no copy: `pull` reads the bucket's lifts and keeps
  none. A `pull` that kept a copy for it is a later step (DEVIATIONS 105).
- **DEVIATIONS 25 is closed** (DEVIATIONS 115): `fetch_lsrs.py` and
  `fetch_calendar_archive.py --listing` follow no redirect now, so every
  General Court request the night makes stops at a redirect, with a
  record. Nobody has seen either page redirect in the ordinary way. If one
  does, the first night after the merge records a refusal that is yours,
  and the "a refusal is yours" check emails you.
- **The operator checklist** (`reports/cloud/CLOUD_MOVE.md`, on the laptop)
  is not in the repository. Steps 2 to 4 above are what it gains: the third
  check, what it means, the read-only key, the three settings and the off
  switches.
