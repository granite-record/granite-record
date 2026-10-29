# The guard's rows (D6), for the owner to apply

`.claude/hooks/guard.py`, and preflight's table of what it must stop
(`_assistant_guard`), are the owner's to change (CLAUDE.md). Nothing on this
branch changes either. The design's D6 asks the guard to ask before five more
calls:

- `src/ops/cloud.py clear-refusal`: it frees GitHub's night to ask the General
  Court again;
- `src/ops/cloud.py send-refusal`: it stops the night;
- `netcheck.py`: seven requests to the General Court's web server, which
  while GitHub may be testing a refusal is two machines asking at once;
- `gh run rerun`: it could repeat a job that asks the General Court or
  deploys. `github.run_attempt == '1'` already keeps a re-run of `knock.yml`
  out of `gc-night` (H1), so this row is defence in depth;
- `gh run cancel`: it could drop a night waiting in `gc-night`.

Today the guard lets all five through. It already asks before `refusal.py
--clear`, `snapshot_gencourt.py` (the knock included), `gh workflow run`,
`gh variable`, `gh secret`, an edit under `.github/workflows`, and every call
of the GitHub tool `actions_run_trigger`, which covers re-runs and cancels
made through it.

The guard and preflight's table are one change: the table's new rows fail
until the guard has its new rows. So both go in one commit, made by the owner
or on the owner's word.

## 1. The rows in `.claude/hooks/guard.py`

In `bash()`, section 5 ("Scripts that ask the General Court, or change what is
live"), after the `cloud.py` row for `push|seed-kit|state-up`:

```python
            if name == "cloud.py" and re.search(r"\b(?:clear-refusal|send-refusal)\b", seg):
                return "ask", ("clear-refusal frees GitHub's night to ask the General Court "
                               "again, and send-refusal stops it: the person's decision, after "
                               "netcheck.py has said what kind of refusal it was (CLAUDE.md).")
            if name == "netcheck.py":
                return "ask", ("netcheck.py asks the General Court's web server, seven requests; "
                               "while GitHub may be testing a refusal itself, NIGHT_KNOCK is set "
                               "to off first. The person's to start (CLAUDE.md).")
```

In `bash()`, section 2, inside `if head in ("gh", "gh.exe") and len(words) > 1:`,
after the `repo delete` row:

```python
            if re.match(r"run\s+(?:rerun|cancel)\b", rest):
                return "ask", ("re-running or cancelling a GitHub run is the person's: a re-run "
                               "can repeat a job that asks the General Court or deploys, and a "
                               "cancel can drop a night waiting in gc-night.")
```

`netcheck.py` is matched by name, because it calls no `refusal.check()`. Its
own guards are `gc_turn()` and `--knock-stopped`, so the guard's general
fetcher row does not catch it.

## 2. The rows C17 adds to preflight's `_assistant_guard` table

Among "Its scripts, and what goes live, only on the person's word":

```python
        (B("python3 src/ops/cloud.py clear-refusal"), "ask"),
        (B("python3 src/ops/cloud.py send-refusal"), "ask"),
        (B("python3 netcheck.py"), "ask"),
        (B("python3 netcheck.py --knock-stopped"), "ask"),
        (B("gh run rerun 123 --failed"), "ask"),
        (B("gh run rerun 123 --job 456"), "ask"),
        (B("gh run rerun 123"), "ask"),
        (B("gh run cancel 123"), "ask"),
```

Among "Ordinary work", so that the new rows do not ask too much:

```python
        (B("python3 refusal.py"), "allow"),
        (B("python3 refusal.py --knock-look"), "allow"),
        (B("gh run list --workflow knock.yml"), "allow"),
        (B("gh run view 123 --log"), "allow"),
```

(`python3 src/ops/cloud.py pull` is already there as "allow".)

## 3. What `decide()` says, today and with the rows

The guard's own `decide()` was run offline on these calls. It was run on the
guard as it stands, and on its source with the two rows above laid over it in
memory. No file was changed.

| Call | Today | With the rows |
|---|---|---|
| `python3 src/ops/cloud.py clear-refusal` | allow | ask |
| `python3 src/ops/cloud.py send-refusal` | allow | ask |
| `python3 netcheck.py` | allow | ask |
| `python3 netcheck.py --knock-stopped` | allow | ask |
| `python netcheck.py` | allow | ask |
| `gh run rerun 123 --failed` | allow | ask |
| `gh run rerun 123 --job 456` | allow | ask |
| `gh run rerun 123` | allow | ask |
| `gh run cancel 123` | allow | ask |
| `gh workflow run knock.yml --ref dev` | ask | ask |
| `python3 src/fetch/gc_web/snapshot_gencourt.py --knock` | ask | ask |
| `python3 refusal.py --clear` | ask | ask |
| Edit `.github/workflows/knock.yml` | ask | ask |
| `gh variable set NIGHT_KNOCK --body off` | ask | ask |
| `gh secret set HEALTHCHECKS_PERSON_URL` | ask | ask |
| `mcp__github__actions_run_trigger` (a re-run) | ask | ask |
| `python3 src/ops/cloud.py pull --changes-only` | allow | allow |
| `python3 refusal.py` | allow | allow |
| `python3 refusal.py --knock-look` | allow | allow |
| `gh run list --workflow knock.yml` | allow | allow |
| `gh run view 123 --log` | allow | allow |
| `grep -n netcheck CLAUDE.md` | allow | allow |
| `python3 preflight.py --code` | allow | allow |

All 23 calls come out as the table wants once the rows are applied.

## 4. Found while checking these; not in the design

`gh api` sends a POST in two forms the guard's write test does not read. The
test is `(?:-X|--method)\s*(?:PUT|PATCH|DELETE|POST)`:

| Call | Today |
|---|---|
| `gh api -X POST repos/o/r/actions/runs/1/rerun` | ask |
| `gh api --method=POST repos/o/r/actions/runs/1/rerun` | **allow** |
| `gh api repos/o/r/actions/runs/1/cancel -f x=1` | **allow** (gh sends a POST when fields are given without `-X`) |

So a re-run or cancel through `gh api` gets past the `gh run` rows above. Two
changes would close it, if the owner wants them:

- accept `=` as well as a space after `--method`:
  `(?:-X|--method)[\s=]*(?:PUT|PATCH|DELETE|POST)`;
- ask for any `gh api` that passes `-f`, `-F`, `--field`, `--raw-field` or
  `--input` without `-X GET` / `--method GET`.

The second does not touch `knock.yml`'s `quiet` job, which runs `gh api -X GET`.
The guard reads an assistant's commands, not the workflows', so the job is
outside it either way.
