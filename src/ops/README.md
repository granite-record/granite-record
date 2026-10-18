# src/ops/

The tools that keep the site running rather than build it: what the
workflows, the morning triage and a person run by its path.

- `cloud.py` -- the private R2 bucket: the nightly's kit and state going down
  and up, the built site handed between jobs, the laptop's backup and its
  pull. Both workflows run it as `python src/ops/cloud.py ...`.
- `livestreams.py` -- the night's new livestreams, indexed, captioned and
  read into the start times (`--since-state` in the nightly workflow,
  `--markers` in the build, `--catch-up` by hand on the laptop). It is the
  one script outside `src/fetch/youtube/` that asks YouTube, and preflight
  holds it to that. Since 17 October 2026 `--to-inbox` is the laptop's
  evening job under Task Scheduler: it asks YouTube for what the night's
  state lists as waiting and puts each caption file in the bucket's captions
  inbox, which the night takes with `--since-state --inbox` (cloud.py
  `inbox-down` before it, `inbox-clear` after the state goes back).
- `compile_reports.py` -- the reader reports from the report box's database,
  screened for the morning triage; the person's production pull.
- `inventory.py` and `handoff.py` -- a session's first and third commands:
  every file and its version, and `STATE.md` with the counts as measured.

Run each from the repository root, `python3 src/ops/inventory.py`; each finds
the rest of the code by bare name through `_paths.py`. They moved here from
the root in the root tidy (8 October 2026), and the workflows, the morning
triage's commands and the documents name the new paths.

Does not belong here: a step of the build (`src/parse/`, `src/pages/` and the
rest, in `build_all.py`'s `plan()`), or a fetch from the General Court
(`src/fetch/gc_web/`). `build_all.py`, `nightly.py`, `preflight.py`,
`refusal.py` and `netcheck.py` stay at the root, where a person or a workflow
names them. The laptop's evening job, `laptop_evening.py`, which Task
Scheduler ran there, went to `obsolete/` on 10 October 2026, when the night
took the captions over; YouTube then refused the night, and the captions
inbox (17 October 2026) gave the laptop back an evening job that writes no
state: `python3 src/ops/livestreams.py --to-inbox`.

## The captions inbox's evening job (17 October 2026)

Once by hand first, in cmd: what it would ask for and send, then a real run.

    cd /d <checkout>
    python3 -X utf8 src\ops\livestreams.py --to-inbox --dry-run
    python3 -X utf8 src\ops\livestreams.py --to-inbox

Then registered with Task Scheduler, in cmd, from any folder, as one line:

    schtasks /create /tn "Granite Record captions inbox" /sc daily /st 19:30 /tr "cmd /c cd /d <checkout> && python3 -X utf8 src\ops\livestreams.py --to-inbox >> logs\captions-inbox.log 2>&1" /f

- `<checkout>` is the folder the repository is cloned into (for example
  `C:\code\granite-record`). `cd /d <checkout>` is in the task's own command because schtasks has no
  start-in folder: without it the task starts in System32, where nothing of
  this repository, `secrets.json` included, is found.
- `-X utf8`: output redirected to a file is otherwise written in the ANSI
  code page, and a recording's title with a character outside it would stop
  the run part way.
- `>>` appends each evening's run to `logs\captions-inbox.log`; the first
  line of each run carries its time.
- The command given to `/tr` is 103 characters, inside schtasks' limit of 261.
- With no `/ru`, the task is registered under your own account as "Run only
  when user is logged on" (Logon Mode: Interactive only), and it must stay
  that way: `python3` is the WindowsApps alias, which exists only in your
  logged-on session. An evening the laptop is off or signed out is skipped,
  and the next one takes up whatever still waits.

To see that it ran:

    schtasks /query /tn "Granite Record captions inbox" /v /fo list | findstr /c:"Last Run Time" /c:"Last Result" /c:"Logon Mode"
    findstr /c:"LIVESTREAMS TO-INBOX" <checkout>\logs\captions-inbox.log

Last Result 0 is a run that finished, a YouTube refusal included (its line in
the log says so); 1 is the bucket, the state in it or a send failing; 3 is
yt-dlp not installed; 9009 is `python3` not found. The next morning the
night's verdict counts what it took: "captioned tonight", the inbox's share
beside it.

Task Scheduler cannot tell a refused evening from a good one, so the night
does (18 October 2026). Each run adds a record of itself to the bucket,
`inbox/laptop/<when it ran>.json`: what it asked and sent, and the laptop's
latest refusal by YouTube and its hold. The night's verdict prints that
refusal beside GitHub's machine's, says what the run sent, and warns -- on
the run's page and to the warnings' Healthchecks check -- when there is no
record, when the newest is two evenings old, or when nothing has arrived in
the inbox for three days while recordings wait.
